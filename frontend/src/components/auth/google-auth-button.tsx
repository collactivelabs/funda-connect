"use client";

import { Button } from "@/components/ui/button";

interface GoogleAuthButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export function GoogleAuthButton({ label, onClick, disabled = false }: GoogleAuthButtonProps) {
  return (
    <Button type="button" variant="outline" className="w-full" onClick={onClick} disabled={disabled}>
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="size-4"
      >
        <path
          fill="#EA4335"
          d="M12 10.2v3.9h5.5c-.2 1.2-.9 2.3-1.9 3.1l3 2.3c1.8-1.6 2.9-4 2.9-6.9 0-.7-.1-1.5-.2-2.2H12Z"
        />
        <path
          fill="#34A853"
          d="M12 21c2.6 0 4.7-.9 6.3-2.5l-3-2.3c-.8.6-1.9 1-3.3 1-2.6 0-4.8-1.7-5.5-4.1H3.4v2.5A9.5 9.5 0 0 0 12 21Z"
        />
        <path
          fill="#4A90E2"
          d="M6.5 13.1a5.7 5.7 0 0 1 0-3.7V6.9H3.4a9.5 9.5 0 0 0 0 8.7l3.1-2.5Z"
        />
        <path
          fill="#FBBC05"
          d="M12 6.8c1.4 0 2.7.5 3.7 1.4l2.8-2.8A9.4 9.4 0 0 0 3.4 6.9l3.1 2.5c.7-2.4 2.9-4.1 5.5-4.1Z"
        />
      </svg>
      {label}
    </Button>
  );
}
