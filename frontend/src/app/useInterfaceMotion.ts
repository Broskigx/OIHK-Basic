import { animate, stagger, type JSAnimation } from "animejs";
import { useEffect, type RefObject } from "react";
import type { PlatformArea } from "./navigation";

function motionIsReduced(): boolean {
  return document.documentElement.classList.contains("reduce-motion")
    || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Shared motion language for the platform shell. The animations deliberately
 * target stable, semantic surfaces so every workspace gets the same entrance
 * rhythm without coupling feature components to Anime.js.
 */
export function useInterfaceMotion(area: PlatformArea, shellRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const shell = shellRef.current;
    if (!shell || motionIsReduced()) return;

    const animations: JSAnimation[] = [];
    const frame = window.requestAnimationFrame(() => {
      const navigation = shell.querySelectorAll<HTMLElement>(".platform-nav-item");
      const chrome = shell.querySelectorAll<HTMLElement>(
        ".platform-brand, .platform-case-context, .platform-search, .platform-topbar-right > *",
      );

      // Guarded like the entrance animations below: Anime.js accepts an empty
      // target list, warns on the console and returns an animation that drives
      // nothing. A shell rendered without navigation is a legitimate state
      // during onboarding, and it should not print a warning per mount.
      if (navigation.length) {
        animations.push(animate(navigation, {
          opacity: { from: 0 },
          x: { from: -10 },
          delay: stagger(24),
          duration: 420,
          ease: "outQuart",
        }));
      }
      if (chrome.length) {
        animations.push(animate(chrome, {
          opacity: { from: 0 },
          y: { from: -8 },
          delay: stagger(28),
          duration: 460,
          ease: "outQuart",
        }));
      }
    });

    return () => {
      window.cancelAnimationFrame(frame);
      animations.forEach((animation) => animation.cancel());
    };
  }, [shellRef]);

  useEffect(() => {
    const shell = shellRef.current;
    if (!shell || motionIsReduced()) return;

    const animations: JSAnimation[] = [];
    const frame = window.requestAnimationFrame(() => {
      const activeNavigation = shell.querySelector<HTMLElement>(".platform-nav-item.active");
      const headline = shell.querySelectorAll<HTMLElement>(
        ".platform-main .platform-workspace-header, .platform-main .dashboard-hero, .platform-main .platform-inline-error, .platform-main .platform-inline-success",
      );
      const surfaces = Array.from(shell.querySelectorAll<HTMLElement>(
        ".platform-main .dashboard-metric, .platform-main .dashboard-panel, .platform-main .platform-section, .platform-main .platform-investigations-toolbar, .platform-main .platform-investigations-table-wrap, .platform-main .platform-investigations-detail, .platform-main .settings-layout, .platform-main .copilot-layout, .platform-main .platform-graph-layout, .platform-main .system-link-power-card, .platform-main .timeline-shell",
      )).slice(0, 28);

      if (activeNavigation) {
        animations.push(animate(activeNavigation, {
          scale: [{ to: 1.025, duration: 150 }, { to: 1, duration: 300 }],
          ease: "outQuart",
        }));
        const icon = activeNavigation.querySelector("svg");
        if (icon) {
          animations.push(animate(icon, {
            rotate: { from: -12 },
            scale: [{ to: 1.16, duration: 170 }, { to: 1, duration: 300 }],
            ease: "outBack",
          }));
        }
      }

      if (headline.length) {
        animations.push(animate(headline, {
          opacity: { from: 0 },
          y: { from: 14 },
          duration: 520,
          delay: stagger(45),
          ease: "outExpo",
        }));
      }

      if (surfaces.length) {
        animations.push(animate(surfaces, {
          opacity: { from: 0 },
          y: { from: 18 },
          scale: { from: 0.992 },
          delay: stagger(34, { start: 90 }),
          duration: 560,
          ease: "outExpo",
        }));
      }
    });

    return () => {
      window.cancelAnimationFrame(frame);
      animations.forEach((animation) => animation.cancel());
    };
  }, [area, shellRef]);
}
