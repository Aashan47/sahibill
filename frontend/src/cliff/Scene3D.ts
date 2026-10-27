// The 200-unit cliff in 3D: a meter whose display rolls the units, and a "bill tower" of one bar per 10
// units, each as tall as the rate those units are charged at, so the tower's area is the energy charge.
// Loaded only when the scene scrolls into view; rendering pauses off-screen.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { LIMIT, rateOfUnit, type Status } from "./model";

const BARS = 40;            // 400 units at 10 units per bar
const STEP = 0.24;          // bar spacing along x
const HEIGHT_PER_RS = 0.09; // bar height per Rs/kWh
const COLORS = { protected: new THREE.Color("#4b4fa6"), unprotected: new THREE.Color("#a86412"), empty: new THREE.Color("#c9d3dc") };

export interface SceneState {
  unitsRead: number;
  unitsBilled: number;
  status: Status;
}

export class CliffScene {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(36, 4 / 3, 0.1, 100);
  private bars: THREE.Mesh[] = [];
  private targets: { h: number; color: THREE.Color; on: boolean }[] = [];
  private world = new THREE.Group();
  private lcd: { canvas: HTMLCanvasElement; tex: THREE.CanvasTexture; shown: number; target: number };
  private frame = 0;
  private running = false;
  private visible = true;
  private clock = new THREE.Clock();
  private io: IntersectionObserver;
  private ro: ResizeObserver;

  constructor(private host: HTMLElement, private still: boolean) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(this.renderer.domElement);
    this.renderer.domElement.setAttribute("aria-hidden", "true");

    this.camera.position.set(1.4, 5.2, 13.8);   // a three-quarter view that keeps the meter and the whole tower in frame
    this.camera.lookAt(2.0, 1.4, 0);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a96a8, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(4, 8, 6);
    this.scene.add(sun);
    this.scene.add(this.world);

    // floor
    const floor = new THREE.Mesh(new RoundedBoxGeometry(14, 0.12, 3.2, 2, 0.05),
      new THREE.MeshStandardMaterial({ color: 0xe4e9ee, roughness: 0.9 }));
    floor.position.set(2.2, -0.06, 0);
    this.world.add(floor);

    // meter
    const meter = new THREE.Group();
    meter.position.set(-3.1, 0, 0);
    const body = new THREE.Mesh(new RoundedBoxGeometry(2.2, 3.0, 1.1, 4, 0.18),
      new THREE.MeshStandardMaterial({ color: 0xf3f1ea, roughness: 0.55 }));
    body.position.y = 1.5;
    meter.add(body);
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 160;
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    const screen = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 0.53), new THREE.MeshBasicMaterial({ map: tex }));
    screen.position.set(0, 2.1, 0.56);
    meter.add(screen);
    for (const x of [-0.45, 0.45]) {
      const t = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.25, 20), new THREE.MeshStandardMaterial({ color: 0x33367a }));
      t.position.set(x, 0.75, 0.6);
      t.rotation.x = Math.PI / 2;
      meter.add(t);
    }
    this.world.add(meter);
    this.lcd = { canvas, tex, shown: 0, target: 0 };

    // bill tower
    const geo = new THREE.BoxGeometry(STEP * 0.78, 1, 1.1);
    geo.translate(0, 0.5, 0);
    for (let i = 0; i < BARS; i++) {
      const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: COLORS.empty, roughness: 0.6 }));
      m.position.set(i * STEP, 0, 0);
      m.scale.y = 0.001;
      m.visible = false;
      this.bars.push(m);
      this.targets.push({ h: 0.001, color: COLORS.empty.clone(), on: false });
      this.world.add(m);
    }

    // the 200-unit plane, dashed outline
    const limitX = (LIMIT / 10) * STEP - STEP / 2;
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 4.2),
      new THREE.MeshBasicMaterial({ color: 0x1b2a41, transparent: true, opacity: 0.06, side: THREE.DoubleSide, depthWrite: false }));
    plane.rotation.y = Math.PI / 2;
    plane.position.set(limitX, 2.1, 0);
    this.world.add(plane);
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(1.6, 4.2)),
      new THREE.LineDashedMaterial({ color: 0x1b2a41, dashSize: 0.14, gapSize: 0.1 }));
    outline.rotation.y = Math.PI / 2;
    outline.position.copy(plane.position);
    outline.computeLineDistances();
    this.world.add(outline);

    this.io = new IntersectionObserver(([e]) => {
      this.visible = e.isIntersecting;
      if (this.visible) this.start();
    });
    this.io.observe(host);
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.resize();
    this.drawLcd(0);
  }

  set(state: SceneState) {
    const shown = Math.min(state.unitsBilled, BARS * 10);
    for (let i = 0; i < BARS; i++) {
      const first = i * 10 + 1;
      const on = first <= shown;
      const rate = on ? rateOfUnit(state.status, first, state.unitsBilled) : 0;
      const t = this.targets[i];
      t.on = on;
      t.h = on ? Math.max(0.02, rate * HEIGHT_PER_RS) : 0.001;
      t.color = on ? COLORS[state.status].clone() : COLORS.empty.clone();
    }
    this.lcd.target = state.unitsRead;
    this.start();
  }

  private start() {
    if (this.running) return;
    this.running = true;
    this.clock.getDelta();
    const tick = () => {
      if (!this.visible) {
        this.running = false;
        return;
      }
      const dt = Math.min(this.clock.getDelta(), 0.05);
      const k = this.still ? 1 : 1 - Math.pow(0.0015, dt);
      let moving = false;
      this.bars.forEach((b, i) => {
        const t = this.targets[i];
        const mat = b.material as THREE.MeshStandardMaterial;
        b.scale.y += (t.h - b.scale.y) * k;
        mat.color.lerp(t.color, k);
        b.visible = t.on || b.scale.y > 0.02;     // empty slots are not drawn
        if (Math.abs(t.h - b.scale.y) > 0.002) moving = true;
      });
      if (Math.abs(this.lcd.target - this.lcd.shown) > 0.5) {
        this.lcd.shown += (this.lcd.target - this.lcd.shown) * k;
        moving = true;
      } else this.lcd.shown = this.lcd.target;
      this.drawLcd(Math.round(this.lcd.shown));
      if (!this.still) this.world.rotation.y = Math.sin(this.clock.elapsedTime * 0.25) * 0.12;
      this.renderer.render(this.scene, this.camera);
      if (this.still && !moving) {
        this.running = false;
        return;
      }
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  private drawLcd(n: number) {
    const c = this.lcd.canvas.getContext("2d")!;
    c.fillStyle = "#c8d6be";
    c.fillRect(0, 0, 512, 160);
    c.fillStyle = "#1b2a41";
    c.font = "bold 104px 'Courier New', monospace";
    c.textBaseline = "middle";
    c.fillText(String(Math.max(0, n)).padStart(6, "0"), 24, 84);
    c.font = "bold 30px sans-serif";
    c.fillText("kWh", 420, 128);
    this.lcd.tex.needsUpdate = true;
  }

  private resize() {
    const w = this.host.clientWidth || 640;
    const h = Math.round(w * 0.62);
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = "100%";
    this.renderer.domElement.style.height = "auto";
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    cancelAnimationFrame(this.frame);
    this.io.disconnect();
    this.ro.disconnect();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
