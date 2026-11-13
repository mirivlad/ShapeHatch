import { useEffect, useMemo, useRef, useState } from "react";
import { type ThreeEvent } from "@react-three/fiber";
import { BufferGeometry, Plane, Vector3 } from "three";

type Props = {
 bounds:number[]; position:[number,number]; surfaceZ:number;
 contour:number[][]; onMove:(x:number,y:number)=>void;
 onDragging:(active:boolean)=>void;
};

export function TextHandle({bounds,position,surfaceZ,contour,onMove,onDragging}:Props) {
 const [active,setActive]=useState(false);
 const origin=useRef<{x:number;y:number;cursor:Vector3}|null>(null);
 const z=surfaceZ+1.25;
 const width=Math.max(1,bounds[2]-bounds[0]);
 const height=Math.max(1,bounds[3]-bounds[1]);
 const plane=useMemo(()=>new Plane(new Vector3(0,0,1),-z),[z]);
 const frame=useMemo(()=>new BufferGeometry().setFromPoints([
  new Vector3(position[0]-width/2-1,position[1]-height/2-1,z),
  new Vector3(position[0]+width/2+1,position[1]-height/2-1,z),
  new Vector3(position[0]+width/2+1,position[1]+height/2+1,z),
  new Vector3(position[0]-width/2-1,position[1]+height/2+1,z),
 ]),[position[0],position[1],width,height,z]);
 useEffect(()=>()=>frame.dispose(),[frame]);
 useEffect(()=>()=>{document.body.style.cursor="auto";onDragging(false);},[]);

 function intersect(event:ThreeEvent<PointerEvent>) {
  const hit=new Vector3();
  return event.ray.intersectPlane(plane,hit)?hit:null;
 }
 function begin(event:ThreeEvent<PointerEvent>) {
  if(event.button!==0)return;
  const hit=intersect(event);
  if(!hit)return;
  event.stopPropagation();
  origin.current={x:position[0],y:position[1],cursor:hit};
  (event.target as HTMLElement).setPointerCapture(event.pointerId);
  setActive(true);onDragging(true);
  document.body.style.cursor="grabbing";
 }
 function move(event:ThreeEvent<PointerEvent>) {
  if(!origin.current)return;
  const hit=intersect(event);
  if(!hit)return;
  event.stopPropagation();
  const anchor=origin.current;
  let x=anchor.x+hit.x-anchor.cursor.x;
  let y=anchor.y+hit.y-anchor.cursor.y;
  // Keep the bounding area within the plate AABB; the backend validates
  // the actual rounded/oval outline and the distance to any keyring hole.
  if(contour.length>2) {
   const xs=contour.map(p=>p[0]),ys=contour.map(p=>p[1]);
   const minX=Math.min(...xs)+width/2+0.65;
   const maxX=Math.max(...xs)-width/2-0.65;
   const minY=Math.min(...ys)+height/2+0.65;
   const maxY=Math.max(...ys)-height/2-0.65;
   if(minX<=maxX)x=Math.min(maxX,Math.max(minX,x));
   if(minY<=maxY)y=Math.min(maxY,Math.max(minY,y));
  }
  x=Math.min(150,Math.max(-150,x));
  y=Math.min(100,Math.max(-100,y));
  onMove(Math.round(x*100)/100,Math.round(y*100)/100);
 }
 function end(event:ThreeEvent<PointerEvent>) {
  if(!origin.current)return;
  event.stopPropagation();
  const canvas=event.target as HTMLElement|null;
  if(canvas?.hasPointerCapture(event.pointerId))
   canvas.releasePointerCapture(event.pointerId);
  origin.current=null;setActive(false);onDragging(false);
  document.body.style.cursor="auto";
 }

 return <>
  <lineLoop geometry={frame} renderOrder={20}>
   <lineBasicMaterial color="#cf802c" transparent opacity={0.8} depthTest={false}/>
  </lineLoop>
  <mesh position={[position[0],position[1],z]} renderOrder={30}
   onPointerOver={e=>{e.stopPropagation();document.body.style.cursor=active?"grabbing":"grab";}}
   onPointerOut={e=>{e.stopPropagation();if(!active)document.body.style.cursor="auto";}}
   onPointerDown={begin} onPointerMove={move}
   onPointerUp={end} onPointerCancel={end}>
   <sphereGeometry args={[2.6,20,14]}/>
   <meshBasicMaterial color="#ffb25b" depthTest={false}/>
  </mesh>
  <mesh position={[position[0],position[1],z+0.02]} renderOrder={31}>
   <ringGeometry args={[2.7,3.45,28]}/>
   <meshBasicMaterial color="#ffffff" depthTest={false}/>
  </mesh>
 </>;
}
