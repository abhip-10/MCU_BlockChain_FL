"""
Pygame real-time canvas for LoRa mesh simulation.
Canvas: 1280x780  |  Mesh area: 880px wide  |  Side panel: 400px wide
"""
import math
import time
from dataclasses import dataclass, field

import pygame

from sim.event_bus import EventBus

# ---------- layout constants ----------
W, H = 1280, 780
CANVAS_W = 860
PANEL_X  = CANVAS_W
PANEL_W  = W - CANVAS_W
NODE_R   = 14
FPS      = 60

# ---------- colours ----------
BG        = (15,  15,  25)
PANEL_BG  = (22,  22,  35)
EDGE_COL  = (60,  60,  90)
WHITE     = (240, 240, 240)
YELLOW    = (255, 230,  80)
CYAN      = (80,  220, 220)
RED       = (220,  60,  60)
GREEN     = (60,  200,  80)
GREY      = (120, 120, 140)
ORANGE    = (255, 160,  40)

PACKET_COLORS = {
    "GPS_UPDATE": (80,  180, 255),
    "FL_ROUND":   (180, 80,  255),
    "FALL":       (255, 80,  80),
    "DISTRESS":   (255, 140, 40),
    "vote":       (200, 200, 80),
    "gossip":     (80,  220, 150),
    "default":    (200, 200, 200),
}


def _rep_color(score: float) -> tuple:
    r = int(255 * (1.0 - score))
    g = int(255 * score)
    return (min(r, 255), min(g, 255), 40)


@dataclass
class Packet:
    src:      tuple   # canvas (x, y)
    dst:      tuple
    color:    tuple
    dropped:  bool    = False
    progress: float   = 0.0
    speed:    float   = 0.9   # fraction per second
    alive:    bool    = True

    def update(self, dt: float) -> None:
        if not self.alive:
            return
        self.progress += self.speed * dt
        if self.progress >= 1.0:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.alive:
            return
        t = min(self.progress, 1.0)
        x = self.src[0] + (self.dst[0] - self.src[0]) * t
        y = self.src[1] + (self.dst[1] - self.src[1]) * t

        if self.dropped:
            alpha = max(0, int(255 * (1.0 - t * 1.5)))
            r, g, b = self.color
            dot = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(dot, (r, g, b, alpha), (6, 6), 5)
            surface.blit(dot, (int(x) - 6, int(y) - 6))
        else:
            pygame.draw.circle(surface, self.color, (int(x), int(y)), 5)


@dataclass
class FlashRing:
    pos:     tuple
    color:   tuple
    radius:  float = 0.0
    alive:   bool  = True

    def update(self, dt: float) -> None:
        self.radius += 60 * dt
        if self.radius > NODE_R * 3:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.alive:
            return
        alpha = max(0, int(255 * (1.0 - self.radius / (NODE_R * 3))))
        r, g, b = self.color
        ring = pygame.Surface((int(self.radius * 2 + 4), int(self.radius * 2 + 4)),
                              pygame.SRCALPHA)
        pygame.draw.circle(ring, (r, g, b, alpha),
                           (int(self.radius + 2), int(self.radius + 2)),
                           int(self.radius), 2)
        surface.blit(ring, (int(self.pos[0] - self.radius - 2),
                            int(self.pos[1] - self.radius - 2)))


class Visualizer:
    def __init__(self, bus: EventBus) -> None:
        pygame.init()
        self._screen  = pygame.display.set_mode((W, H))
        pygame.display.set_caption("LoRa Mesh — Live Simulation")
        self._clock   = pygame.time.Clock()
        self._bus     = bus
        self._font_s  = pygame.font.SysFont("monospace", 12)
        self._font_m  = pygame.font.SysFont("monospace", 14, bold=True)
        self._font_l  = pygame.font.SysFont("monospace", 18, bold=True)

        # dynamic mesh state
        self._cpos:     dict[str, tuple]  = {}   # node_id -> canvas (x,y)
        self._rep:      dict[str, float]  = {}   # node_id -> score
        self._flagged:  set[str]          = set()
        self._edge_pdr: dict[tuple, float]= {}   # (a,b) -> pdr
        self._packets:  list[Packet]      = []
        self._rings:    list[FlashRing]   = []

        # side-panel log
        self._log:      list[str]         = []
        self._scenario: str               = "Initialising..."
        self._paused:   bool              = False
        self._overlay:  bool              = True

        self._last_time = time.time()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def set_mesh(self, positions: dict, edge_pdrs: dict, reputations: dict) -> None:
        """Called from main thread to initialise or re-initialise mesh layout."""
        margin = 60
        xs = [p[0] for p in positions.values()]
        ys = [p[1] for p in positions.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        rx = max_x - min_x or 1
        ry = max_y - min_y or 1

        self._cpos = {}
        for nid, (px, py) in positions.items():
            cx = int(margin + (px - min_x) / rx * (CANVAS_W - 2 * margin))
            cy = int(margin + (py - min_y) / ry * (H - 2 * margin))
            self._cpos[nid] = (cx, cy)

        self._edge_pdr = edge_pdrs
        self._rep      = dict(reputations)
        self._flagged  = set()
        self._packets  = []
        self._rings    = []

    def tick(self) -> str:
        """Call once per frame. Returns 'next', 'quit', or ''."""
        now = time.time()
        dt  = now - self._last_time
        self._last_time = now

        result = self._handle_events()
        if result in ("next", "quit"):
            return result

        if not self._paused:
            self._drain_bus()
            self._update_particles(dt)

        self._draw()
        self._clock.tick(FPS)
        return ""

    # ------------------------------------------------------------------ #
    #  Internal: event handling                                            #
    # ------------------------------------------------------------------ #

    def _handle_events(self) -> str:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return "quit"
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_q:
                    return "quit"
                if ev.key == pygame.K_SPACE:
                    return "next"
                if ev.key == pygame.K_p:
                    self._paused = not self._paused
                if ev.key == pygame.K_o:
                    self._overlay = not self._overlay
                if ev.key == pygame.K_f:
                    self._bus.speed = min(self._bus.speed * 2, 16.0)
                    self._log_msg(f"Speed x{self._bus.speed:.0f}")
                if ev.key == pygame.K_s:
                    self._bus.speed = max(self._bus.speed / 2, 0.25)
                    self._log_msg(f"Speed x{self._bus.speed:.1f}")
        return ""

    def _drain_bus(self) -> None:
        for _ in range(30):   # max events per frame
            ev = self._bus.poll()
            if ev is None:
                break
            self._process(ev)

    def _process(self, ev: dict) -> None:
        t = ev.get("type", "")

        if t == "mesh_reset":
            self._scenario = ev.get("scenario", "")
            self._log_msg(f"--- {self._scenario} ---")
            # set_mesh called explicitly from main thread before scenario starts

        elif t == "reputation_change":
            nid   = ev["node_id"]
            score = ev["score"]
            self._rep[nid] = score
            if score < 0.20:
                self._flagged.add(nid)
                self._log_msg(f"FLAGGED {nid}  score={score:.2f}")
                if nid in self._cpos:
                    self._rings.append(FlashRing(self._cpos[nid], RED))
            else:
                self._flagged.discard(nid)

        elif t == "block_proposed":
            nid = ev["proposer"]
            if nid in self._cpos:
                color = PACKET_COLORS.get(ev.get("event_type", ""), PACKET_COLORS["default"])
                self._rings.append(FlashRing(self._cpos[nid], color))

        elif t == "vote_cast":
            src = ev["voter"]
            dst = ev["proposer"]
            if src in self._cpos and dst in self._cpos:
                color = GREEN if ev["approved"] else RED
                self._spawn_packet(src, dst, color, dropped=not ev["approved"])

        elif t == "block_committed":
            nid = ev["node_id"]
            if nid in self._cpos:
                self._rings.append(FlashRing(self._cpos[nid], GREEN))
            self._log_msg(f"  COMMIT #{ev['index']} by {nid}")

        elif t == "block_rejected":
            nid = ev["node_id"]
            if nid in self._cpos:
                self._rings.append(FlashRing(self._cpos[nid], RED))
            self._log_msg(f"  REJECT  {nid}: {ev.get('reason','')}")

        elif t == "gossip_hop":
            src = ev["src"]
            dst = ev["dst"]
            if src and dst and src in self._cpos and dst in self._cpos:
                self._spawn_packet(src, dst,
                                   PACKET_COLORS["gossip"],
                                   dropped=ev["dropped"])

        elif t == "fl_round":
            self._log_msg(f"  FL round {ev.get('round','')}  delta={ev.get('delta',0):.4f}")

    def _spawn_packet(self, src_id: str, dst_id: str,
                      color: tuple, dropped: bool = False) -> None:
        self._packets.append(Packet(
            src=self._cpos[src_id],
            dst=self._cpos[dst_id],
            color=color,
            dropped=dropped,
        ))

    def _log_msg(self, msg: str) -> None:
        self._log.append(msg)
        if len(self._log) > 200:
            self._log = self._log[-150:]

    # ------------------------------------------------------------------ #
    #  Internal: update / draw                                             #
    # ------------------------------------------------------------------ #

    def _update_particles(self, dt: float) -> None:
        for p in self._packets:
            p.update(dt)
        self._packets = [p for p in self._packets if p.alive]

        for r in self._rings:
            r.update(dt)
        self._rings = [r for r in self._rings if r.alive]

    def _draw(self) -> None:
        self._screen.fill(BG)

        self._draw_edges()
        self._draw_rings()
        self._draw_packets()
        self._draw_nodes()
        self._draw_panel()

        if self._overlay:
            self._draw_overlay()

        pygame.display.flip()

    def _draw_edges(self) -> None:
        for (a, b), pdr in self._edge_pdr.items():
            if a not in self._cpos or b not in self._cpos:
                continue
            thickness = max(1, int(pdr * 4))
            alpha     = int(40 + pdr * 120)
            r, g, bl  = EDGE_COL
            surf = pygame.Surface((CANVAS_W, H), pygame.SRCALPHA)
            pygame.draw.line(surf, (r, g, bl, alpha),
                             self._cpos[a], self._cpos[b], thickness)
            self._screen.blit(surf, (0, 0))

    def _draw_rings(self) -> None:
        for ring in self._rings:
            ring.draw(self._screen)

    def _draw_packets(self) -> None:
        for pkt in self._packets:
            pkt.draw(self._screen)

    def _draw_nodes(self) -> None:
        now = time.time()
        for nid, pos in self._cpos.items():
            score  = self._rep.get(nid, 0.5)
            color  = _rep_color(score)
            flagged = nid in self._flagged

            # pulsing border for flagged nodes
            if flagged:
                pulse = 0.5 + 0.5 * math.sin(now * 6)
                br    = int(NODE_R + 5 * pulse)
                pygame.draw.circle(self._screen, RED, pos, br, 2)

            pygame.draw.circle(self._screen, color, pos, NODE_R)
            pygame.draw.circle(self._screen, WHITE, pos, NODE_R, 1)

            label = self._font_s.render(nid, True, WHITE)
            self._screen.blit(label, (pos[0] - label.get_width() // 2,
                                      pos[1] + NODE_R + 2))

    def _draw_panel(self) -> None:
        panel = pygame.Surface((PANEL_W, H))
        panel.fill(PANEL_BG)

        y = 10
        title = self._font_l.render("LoRa Mesh Sim", True, CYAN)
        panel.blit(title, (10, y)); y += 30

        scenario = self._font_m.render(self._scenario[:38], True, YELLOW)
        panel.blit(scenario, (10, y)); y += 26

        spd = self._font_s.render(f"Speed x{self._bus.speed:.1f}  |  {'PAUSED' if self._paused else 'RUNNING'}", True, GREY)
        panel.blit(spd, (10, y)); y += 20

        pygame.draw.line(panel, GREY, (10, y), (PANEL_W - 10, y)); y += 8

        # reputation bar
        rep_title = self._font_m.render("Node Reputations", True, WHITE)
        panel.blit(rep_title, (10, y)); y += 20

        for nid in sorted(self._rep.keys()):
            score = self._rep[nid]
            bar_w = int(score * (PANEL_W - 110))
            col   = _rep_color(score)
            pygame.draw.rect(panel, col, (90, y, bar_w, 12))
            pygame.draw.rect(panel, GREY, (90, y, PANEL_W - 110, 12), 1)
            lbl = self._font_s.render(f"{nid[:8]:<8} {score:.2f}", True,
                                      RED if nid in self._flagged else WHITE)
            panel.blit(lbl, (8, y)); y += 16
            if y > H - 160:
                break

        pygame.draw.line(panel, GREY, (10, y + 4), (PANEL_W - 10, y + 4)); y += 10

        # event log (most recent at top)
        log_lines = self._log[-((H - y - 10) // 14):]
        for line in reversed(log_lines):
            txt = self._font_s.render(line[:46], True, GREY)
            panel.blit(txt, (8, y)); y += 14
            if y > H - 10:
                break

        self._screen.blit(panel, (PANEL_X, 0))
        pygame.draw.line(self._screen, GREY, (PANEL_X, 0), (PANEL_X, H))

    def _draw_overlay(self) -> None:
        keys = [
            "SPACE  next scenario",
            "P      pause/resume",
            "F / S  faster/slower",
            "O      hide overlay",
            "Q      quit",
        ]
        y = H - len(keys) * 18 - 10
        for k in keys:
            surf = self._font_s.render(k, True, (160, 160, 180))
            self._screen.blit(surf, (10, y)); y += 18

    def close(self) -> None:
        pygame.quit()
