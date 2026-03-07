import React from "react";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export function Card({ children, className = "", onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") onClick(); } : undefined}
      className={[
        "rounded-2xl border border-[#1f1f1f] bg-[#111111] p-4",
        "transition-all duration-200 ease-out",
        "hover:bg-[#161616] hover:border-[#2a2a2a]",
        "shadow-[0_1px_3px_rgba(0,0,0,0.4)]",
        onClick ? "cursor-pointer active:scale-[0.98] min-h-[44px]" : "",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}
