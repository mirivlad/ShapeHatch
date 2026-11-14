import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { GizmoHelper, GizmoViewcube, OrbitControls } from "@react-three/drei";
import { BufferAttribute, BufferGeometry, DoubleSide, OrthographicCamera, Shape, ShapeGeometry, Vector2, Vector3 } from "three";
import type { InnerContourPreview, Part, Preview } from "./types";
import { MountHandle } from "./MountHandle";
import { TextHandle } from "./TextHandle";
import { MagnetHandles } from "./MagnetHandles";

export type CameraView = "iso" | "top" | "bottom" | "front" | "back" | "left" | "right";

function MeshPart({ part }: { part: Part }) {
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    const verts = new Float32Array(part.vertices.flat());
    g.setAttribute("position", new BufferAttribute(verts, 3));
    g.setIndex(part.faces.flat());
    g.computeVertexNormals();
    return g;
  }, [part]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry}>
    <meshStandardMaterial color={part.color} metalness={0.04} roughness={0.75} side={DoubleSide} />
  </mesh>;
}

function InnerContourHandle({contour, z, selected, onSelect}: {
  contour:InnerContourPreview; z:number; selected:boolean; onSelect:(id:string)=>void
}) {
  const fill = useMemo(()=>{
    const polygon=new Shape(contour.points.map(([x,y])=>new Vector2(x,y)));
    return new ShapeGeometry(polygon);
  },[contour.points]);
  const outline=useMemo(()=>{
    const g=new BufferGeometry();
    g.setFromPoints(contour.points.map(([x,y])=>new Vector3(x,y,0)));
    return g;
  },[contour.points]);
  useEffect(()=>()=>{fill.dispose();outline.dispose();},[fill,outline]);
  return <group position={[0,0,z+0.055]}>
    <mesh geometry={fill} renderOrder={7}
      onClick={event=>{event.stopPropagation();onSelect(contour.id);}}>
      <meshBasicMaterial color={selected?"#FFAE42":"#37A58A"}
        transparent opacity={selected?0.28:0.12} side={DoubleSide}
        depthWrite={false} depthTest={false}/>
    </mesh>
    <lineLoop geometry={outline} renderOrder={8}
      onClick={event=>{event.stopPropagation();onSelect(contour.id);}}>
      <lineBasicMaterial color={selected?"#F28B2B":"#168C79"}
        transparent opacity={selected?1:0.82} depthTest={false}/>
    </lineLoop>
  </group>;
}

function CameraController({ preview, view }: { preview: Preview | null; view: CameraView }) {
  const { camera, controls, size } = useThree();
  const initialized = useRef(false);
  const previousView = useRef<CameraView | null>(null);
  useEffect(() => {
    // Refit when the model first appears or when user changes view;
    // do not unexpectedly reorient the scene on each drag/preview rebuild.
    if (!preview || (initialized.current && previousView.current===view)) return;
    const c = camera as OrthographicCamera;
    if (!c.isOrthographicCamera) return;
    const parts = preview?.parts ?? [];
    const min = new Vector3(Infinity, Infinity, Infinity);
    const max = new Vector3(-Infinity, -Infinity, -Infinity);
    for (const part of parts) {
      for (const [x,y,z] of part.vertices) {
        min.min(new Vector3(x,y,z));
        max.max(new Vector3(x,y,z));
      }
    }
    if (!parts.length) { min.set(-30,-30,0); max.set(30,30,5); }
    const center = min.clone().add(max).multiplyScalar(0.5);
    const extent = max.clone().sub(min);
    const distance = Math.max(extent.length()*2, 80);
    const directions: Record<CameraView,Vector3> = {
      iso:new Vector3(0.8,-1,1.5),
      top:new Vector3(0,0,1),bottom:new Vector3(0,0,-1),
      front:new Vector3(0,-1,0),back:new Vector3(0,1,0),
      left:new Vector3(-1,0,0),right:new Vector3(1,0,0),
    };
    const direction = directions[view].clone().normalize();
    c.position.copy(center).add(direction.multiplyScalar(distance));
    c.up.set(0,1,0);
    if (view==="front" || view==="back") c.up.set(0,0,1);
    if (view==="bottom") c.up.set(0,-1,0);
    c.lookAt(center);
    // Orthographic Canvas default camera frustum is canvas width x height.
    c.zoom = Math.max(0.2, Math.min(size.width,size.height)/Math.max(extent.length()*1.5, 20));
    c.updateProjectionMatrix();
    if (controls && "target" in controls) {
      const orbit = controls as unknown as {target:Vector3;update:()=>void};
      orbit.target.copy(center);
      orbit.update();
    }
    initialized.current=true;
    previousView.current=view;
  }, [camera,controls,preview,view,size.width,size.height]);
  return null;
}

export function Viewer({preview,view,mountEnabled,mountPosition,onMountPositionChange,
  textPosition,onTextPositionChange,selectedContour,onContourSelect,
  magnetEnabled,magnetPositions,onMagnetPositionChange}:{
  preview:Preview|null;view:CameraView;mountEnabled:boolean;
  mountPosition:number|null;onMountPositionChange:(fraction:number)=>void;
  textPosition:[number,number]|null;onTextPositionChange:(x:number,y:number)=>void;
  selectedContour:string|null;onContourSelect:(id:string)=>void;
  magnetEnabled:boolean;magnetPositions:number[][];
  onMagnetPositionChange:(index:number,x:number,y:number)=>void
}) {
  const [dragging,setDragging]=useState(false);
  useEffect(()=>setDragging(false),[mountEnabled,view]);
  return <div className="viewer-canvas">
    <Canvas orthographic camera={{position:[70,-90,130],zoom:5,near:0.01,far:30000}}>
      <color attach="background" args={["#e9eef0"]}/>
      <ambientLight intensity={2}/>
      <directionalLight position={[20,-40,60]} intensity={3}/>
      <directionalLight position={[-30,20,70]} intensity={1.2}/>
      <gridHelper args={[300,30,"#b6c4cd","#d0dbe0"]} rotation={[Math.PI/2,0,0]} position={[0,0,-0.35]}/>
      {preview?.parts.map((part,i)=><MeshPart key={i} part={part}/>)}
      {preview?.inner_contours?.map(contour=><InnerContourHandle key={contour.id}
        contour={contour} z={preview.mount_surface_z}
        selected={selectedContour===contour.id} onSelect={onContourSelect}/>)}
      {mountEnabled && preview && preview.mount_contour?.length>2 &&
       <MountHandle contour={preview.mount_contour}
        fraction={mountPosition??preview.mount_fraction??0}
        surfaceZ={preview.mount_surface_z}
        onChange={onMountPositionChange} onDragging={setDragging}/>}
      {magnetEnabled && preview && magnetPositions.length>0 &&
       <MagnetHandles positions={magnetPositions} contour={preview.mount_contour}
        surfaceZ={preview.magnet_surface_z}
        onMove={onMagnetPositionChange} onDragging={setDragging}/>}
      {preview?.text_bounds_mm && textPosition &&
       <TextHandle bounds={preview.text_bounds_mm} position={textPosition}
        surfaceZ={preview.text_surface_z} contour={preview.mount_contour}
        onMove={onTextPositionChange} onDragging={setDragging}/>}
      <OrbitControls makeDefault enabled={!dragging}
       enableDamping dampingFactor={0.08} minZoom={0.15} maxZoom={35}/>
      <CameraController preview={preview} view={view}/>
      <GizmoHelper alignment="top-right" margin={[74,72]}>
        <GizmoViewcube font="Arial" color="#ffffff" textColor="#334650" hoverColor="#cff1ec" opacity={0.92}/>
      </GizmoHelper>
    </Canvas>
  </div>;
}
