import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./global.css";
import { ConfigProvider, theme } from "antd";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgContainer: '#0f172a',
          colorBgElevated: '#0f172a',
          colorBorder: 'rgba(255, 255, 255, 0.12)',
          colorPrimary: '#0284c7',
          fontFamily: `${import.meta.env.VITE_CHAT_FONT || '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'}, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"`,
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);
