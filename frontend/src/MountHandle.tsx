import { useEffect, useMemo, useState } from "react";
import { type ThreeEvent, useThree } from "@react-three/fiber";
import { BufferGeometry, Vector2, Vector3 } from "three";

type Props = {
  contour: number[][];
  fraction: number;
  surfaceZ: number;
  onChange: (fraction: number) => void;
  onDragging: (dragging: boolean) => void;
};

function pointAt(contour: number[][], fraction: number): [number, number] {
  const count = contour.length - 1;
  const position = (((fraction % 1) + 1) % 1) * count;
  const index = Math.min(count - 1, Math.floor(position));
  const blend = position - index;
  return [
    contour[index][0] * (1 - blend) + contour[index + 1][0] * blend,
    contour[index][1] * (1 - blend) + contour[index + 1][1] * blend,
  ];
}

export function MountHandle({ contour, fraction, surfaceZ, onChange, onDragging }: Props) {
  const { camera, size } = useThree();
  const [dragging, setDragging] = useState(false);
  const marker = pointAt(contour, fraction);
  const z = surfaceZ + 1.4;
  const outline = useMemo(
    () => new BufferGeometry().setFromPoints(contour.map(([x, y]) => new Vector3(x, y, surfaceZ + 0.45))),
    [contour, surfaceZ],
  );

  useEffect(() => () => outline.dispose(), [outline]);

  function nearestFraction(pointer: Vector2): number {
    // Snap in screen space so dragging works in top, isometric and tilted views.
    // Samples are uniformly spaced by the actual contour's arc length.
    const projected = contour.map(([x, y]) => {
      const p = new Vector3(x, y, surfaceZ).project(camera);
      return [(p.x - pointer.x) * size.width / 2, (p.y - pointer.y) * size.height / 2];
    });
    let minimum = Infinity;
    let nearest = 0;
    const segments = projected.length - 1;
    for (let i = 0; i < segments; i++) {
      const [ax, ay] = projected[i], [bx, by] = projected[i + 1];
      const dx = bx - ax, dy = by - ay;
      const length2 = dx * dx + dy * dy;
      const interpolation = length2 < 1e-8 ? 0 :
        Math.max(0, Math.min(1, -(ax * dx + ay * dy) / length2));
      const px = ax + interpolation * dx, py = ay + interpolation * dy;
      const distance2 = px * px + py * py;
      if (distance2 < minimum) {
        minimum = distance2;
        nearest = (i + interpolation) / segments;
      }
    }
    return Math.min(1, Math.max(0, nearest));
  }

  function finish(event: ThreeEvent<PointerEvent>) {
    if (!dragging) return;
    event.stopPropagation();
    const canvas = event.target as HTMLElement | null;
    if (canvas?.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
    setDragging(false);
    onDragging(false);
  }

  return <>
    <lineLoop geometry={outline} renderOrder={11}>
      <lineBasicMaterial color="#008a77" transparent opacity={0.8} depthTest={false} />
    </lineLoop>
    <mesh
      position={[marker[0], marker[1], z]}
      renderOrder={22}
      onPointerOver={e => { e.stopPropagation(); document.body.style.cursor = "grab"; }}
      onPointerOut={e => { e.stopPropagation(); document.body.style.cursor = "auto"; }}
      onPointerDown={event => {
        event.stopPropagation();
        if (event.button !== 0) return;
        (event.target as HTMLElement).setPointerCapture(event.pointerId);
        setDragging(true);
        onDragging(true);
        document.body.style.cursor = "grabbing";
      }}
      onPointerMove={event => {
        if (!dragging) return;
        event.stopPropagation();
        onChange(nearestFraction(event.pointer));
      }}
      onPointerUp={event => { finish(event); document.body.style.cursor = "grab"; }}
      onPointerCancel={event => { finish(event); document.body.style.cursor = "auto"; }}
    >
      <sphereGeometry args={[2.4, 18, 12]}/>
      <meshBasicMaterial color="#00cba2" depthTest={false} />
    </mesh>
    <mesh position={[marker[0], marker[1], z]} renderOrder={23}>
      <ringGeometry args={[2.5, 3.3, 28]}/>
      <meshBasicMaterial color="#ffffff" transparent opacity={0.94} depthTest={false} />
    </mesh>
  </>;
}
