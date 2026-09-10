/**
 * Light · dark · system, as a three-way radio group in the header. The
 * system option is the default and stays honest: it follows the OS live.
 */

import { Monitor, Moon, Sun } from "./icons";
import { cx } from "./ui";
import { useTheme, type ThemeChoice } from "../theme";

const OPTIONS: { value: ThemeChoice; label: string; icon: React.ReactNode }[] = [
  { value: "light", label: "Light", icon: <Sun /> },
  { value: "dark", label: "Dark", icon: <Moon /> },
  { value: "system", label: "System", icon: <Monitor /> },
];

export function ThemeSwitch({ className }: { className?: string }) {
  const { choice, setChoice } = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cx("inline-flex rounded border border-line bg-subtle p-0.5", className)}
    >
      {OPTIONS.map((option) => {
        const checked = option.value === choice;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={option.label}
            title={option.label}
            onClick={() => setChoice(option.value)}
            className={cx(
              "flex size-7 items-center justify-center rounded-sm transition-colors [&>svg]:size-3.5",
              checked ? "bg-card text-ink shadow-sm" : "text-ink-3 hover:text-ink",
            )}
          >
            {option.icon}
          </button>
        );
      })}
    </div>
  );
}
