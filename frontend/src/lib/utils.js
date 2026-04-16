import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names safely. */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/** Format a number as INR currency. */
export function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/** Format a decimal probability as a percentage string. */
export function formatPct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

/** Format a number with comma separators. */
export function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

/** Return Tailwind color classes for a risk label. */
export function getRiskColor(risk) {
  switch (risk) {
    case "High":
      return { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400", dot: "bg-red-500" };
    case "Medium":
      return { bg: "bg-amber-100 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-400", dot: "bg-amber-500" };
    case "Low":
      return { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400", dot: "bg-green-500" };
    default:
      return { bg: "bg-gray-100 dark:bg-gray-800", text: "text-gray-700 dark:text-gray-400", dot: "bg-gray-500" };
  }
}

/** Return Tailwind color classes for a priority level. */
export function getPriorityColor(priority) {
  switch (priority) {
    case "Critical":
      return "text-red-600 dark:text-red-400 font-semibold";
    case "High":
      return "text-orange-600 dark:text-orange-400 font-semibold";
    case "Medium":
      return "text-amber-600 dark:text-amber-400";
    case "Low":
      return "text-green-600 dark:text-green-400";
    default:
      return "text-gray-600 dark:text-gray-400";
  }
}

/** Truncate a string to N characters. */
export function truncate(str, n = 30) {
  return str.length > n ? str.slice(0, n) + "…" : str;
}
