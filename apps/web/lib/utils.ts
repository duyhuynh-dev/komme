import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDigestTime(value: string) {
  const [hourText = "09", minuteText = "00"] = value.split(":");
  const hour = Number.parseInt(hourText, 10);
  const minute = Number.parseInt(minuteText, 10);
  if (Number.isNaN(hour) || Number.isNaN(minute)) {
    return value;
  }

  const period = hour >= 12 ? "PM" : "AM";
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  const minuteLabel = minute.toString().padStart(2, "0");
  return `${hour12}:${minuteLabel} ${period}`;
}
