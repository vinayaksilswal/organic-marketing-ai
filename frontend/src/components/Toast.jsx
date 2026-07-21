import React from 'react';

const Toast = ({ message, isError }) => {
  return (
    <div className={`message ${isError ? 'error' : 'success'}`}>
      {message}
    </div>
  );
};

export default Toast;
