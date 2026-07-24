import aiohttp
import csv
import io
from loguru import logger
from sqlalchemy import select
from database import AsyncSessionLocal, BusinessProfile, Product

async def sync_workspace_catalog(workspace_id: str):
    """
    Fetches the catalog CSV from BusinessProfile.productCatalogUrl
    and syncs the products to the database for this workspace.
    """
    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or not profile.productCatalogUrl:
            logger.info(f"No product catalog URL for workspace {workspace_id}")
            return
        
        catalog_url = profile.productCatalogUrl
        logger.info(f"Fetching catalog for workspace {workspace_id} from {catalog_url}")

        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(catalog_url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch catalog: HTTP {resp.status}")
                        return
                    text = await resp.text()

            # Parse CSV
            reader = csv.DictReader(io.StringIO(text))
            
            # Map common headers to our schema
            def get_val(row, *keys):
                for k in keys:
                    if k in row and row[k]:
                        return str(row[k]).strip()
                    # Also try case-insensitive
                    for row_k, row_v in row.items():
                        if row_k and row_k.strip().lower() == k.lower() and row_v:
                            return str(row_v).strip()
                return None

            products_upserted = 0
            for row in reader:
                title = get_val(row, 'title', 'name', 'product_name')
                if not title:
                    continue
                
                description = get_val(row, 'description', 'desc')
                price_str = get_val(row, 'price', 'sale_price')
                price = None
                if price_str:
                    try:
                        price = float(price_str.replace('$', '').replace(',', '').strip())
                    except ValueError:
                        pass
                
                url = get_val(row, 'url', 'link', 'product_url')
                image_url = get_val(row, 'image_url', 'image', 'image_link', 'picture')
                video_url = get_val(row, 'video_url', 'video', 'video_link')

                # Check if product already exists by URL or title
                stmt = select(Product).where(
                    Product.businessProfileId == workspace_id,
                    Product.title == title
                )
                res = await session.execute(stmt)
                existing = res.scalars().first()

                if existing:
                    existing.description = description
                    existing.price = price
                    existing.url = url
                    existing.imageUrl = image_url
                    existing.videoUrl = video_url
                else:
                    new_product = Product(
                        userId=profile.userId,
                        businessProfileId=workspace_id,
                        title=title,
                        description=description,
                        price=price,
                        url=url,
                        imageUrl=image_url,
                        videoUrl=video_url
                    )
                    session.add(new_product)
                
                products_upserted += 1

            await session.commit()
            logger.info(f"Successfully synced {products_upserted} products for workspace {workspace_id}")

        except Exception as e:
            logger.error(f"Error syncing catalog for workspace {workspace_id}: {e}")
