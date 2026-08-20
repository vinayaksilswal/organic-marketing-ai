import React, { useEffect, useState } from 'react';
import { Star, Quote } from 'lucide-react';
import { API_BASE } from '../config';

const PUBLIC_API = API_BASE.replace('/api/v1', '');

/**
 * What customers said, once a human has approved it being said publicly.
 *
 * Renders NOTHING when there are no approved reviews. A testimonials section
 * holding two placeholder quotes is worse than no section at all — it is the
 * clearest signal on a page that nobody is actually using the product, and it
 * is the first thing a sceptical visitor checks.
 *
 * So this grows into the page rather than waiting for it. The endpoint already
 * degrades to an empty list on any error, which lands here as "render
 * nothing", which is exactly right.
 */
const ReviewWall = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    fetch(`${PUBLIC_API}/api/public/reviews`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d?.reviews?.length) setData(d); })
      .catch(() => { /* the page is fine without this */ });
    return () => { alive = false; };
  }, []);

  if (!data) return null;

  return (
    <section>
      <div className="wrap">
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <span className="eyebrow">From customers</span>
          <h2 className="h2" style={{ margin: '1.1rem auto .9rem', maxWidth: 700 }}>
            What it is doing for the businesses running it
          </h2>
          {data.average != null && (
            <p className="lede" style={{ maxWidth: 520, margin: '0 auto' }}>
              <span className="tnum" style={{ fontWeight: 700, color: 'var(--ink)' }}>
                {data.average}
              </span>{' '}
              out of 5 across {data.count} {data.count === 1 ? 'review' : 'reviews'}.
            </p>
          )}
        </div>

        <div className="grid g3">
          {data.reviews.map((r, i) => (
            <div key={i} className="glass" style={{ padding: '1.6rem' }}>
              <div style={{ display: 'flex', gap: 2, marginBottom: '.8rem' }}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <Star
                    key={n} size={14}
                    color={n <= r.rating ? '#f59e0b' : 'rgba(120,120,140,0.3)'}
                    fill={n <= r.rating ? '#f59e0b' : 'none'}
                  />
                ))}
              </div>
              {r.body && (
                <p style={{ fontSize: '.9rem', lineHeight: 1.65, marginBottom: '.9rem' }}>
                  <Quote size={13} style={{ opacity: .35, marginRight: 4, verticalAlign: 'top' }} />
                  {r.body}
                </p>
              )}
              {(r.author || r.business) && (
                <div style={{ fontSize: '.8rem', color: 'var(--ink-faint)', fontWeight: 600 }}>
                  {[r.author, r.business].filter(Boolean).join(' · ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ReviewWall;
