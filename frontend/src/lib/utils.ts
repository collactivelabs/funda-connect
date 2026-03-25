import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format cents (integer) to ZAR display string: R250.00 */
export function formatZAR(cents: number): string {
  return `R${(cents / 100).toFixed(2)}`;
}

/** Format ISO date string to SAST-friendly display */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-ZA", {
    timeZone: "Africa/Johannesburg",
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Format ISO date string to time display in SAST */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-ZA", {
    timeZone: "Africa/Johannesburg",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Get initials from a name */
export function getInitials(firstName: string, lastName: string): string {
  return `${firstName[0]}${lastName[0]}`.toUpperCase();
}
