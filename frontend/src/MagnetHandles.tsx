import {useMemo,useRef,useState} from "react";
import {type ThreeEvent} from "@react-three/fiber";
import {Plane,Vector3} from "three";

export function MagnetHandles({positions,surfaceZ,contour,onMove,onDragging}:{
  positions:number[][]; surfaceZ:number;contour:number[][];
  onMove:(index:number,x:number,y:number)=>void;onDragging:(active:boolean)=>void;
}) {
  const [active,setActive]=useState<number|null>(null);
  const start=useRef<{index:number;x:number;y:number;point:Vector3}|null>(null);
  const z=surfaceZ===0?-0.6:surfaceZ+0.65;
  const plane=useMemo(()=>new Plane(new Vector3(0,0,1),-z),[z]);
  function cursor(e:ThreeEvent<PointerEvent>) {
    const p=new Vector3();
    return e.ray.intersectPlane(plane,p)?p:null;
  }
  function finish(e:ThreeEvent<PointerEvent>){
    if(!start.current)return;
    e.stopPropagation();
    const target=e.target as HTMLElement;
    if(target.hasPointerCapture(e.pointerId))target.releasePointerCapture(e.pointerId);
    start.current=null;setActive(null);onDragging(false);
    document.body.style.cursor="auto";
  }
  return <>{positions.map(([x,y],i)=><group key={i} position={[x,y,z]}>
    <mesh renderOrder={41}
      onPointerOver={e=>{e.stopPropagation();document.body.style.cursor="grab";}}
      onPointerOut={e=>{e.stopPropagation();if(active===null)document.body.style.cursor="auto";}}
      onPointerDown={e=>{
        if(e.button!==0)return;
        const pt=cursor(e);if(!pt)return;
        e.stopPropagation();
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
        start.current={index:i,x,y,point:pt};setActive(i);onDragging(true);
        document.body.style.cursor="grabbing";
      }}
      onPointerMove={e=>{
        const original=start.current;
        if(!original||original.index!==i)return;
        const pt=cursor(e);if(!pt)return;
        e.stopPropagation();
        let xx=original.x+pt.x-original.point.x;
        let yy=original.y+pt.y-original.point.y;
        if(contour.length>2){
          const xs=contour.map(a=>a[0]),ys=contour.map(a=>a[1]);
          xx=Math.max(Math.min(...xs),Math.min(Math.max(...xs),xx));
          yy=Math.max(Math.min(...ys),Math.min(Math.max(...ys),yy));
        }
        onMove(i,Math.round(xx*100)/100,Math.round(yy*100)/100);
      }}
      onPointerUp={finish} onPointerCancel={finish}>
      <sphereGeometry args={[2.3,18,12]}/>
      <meshBasicMaterial color={active===i?"#f39838":"#a642cb"} depthTest={false}/>
    </mesh>
    <mesh renderOrder={42}>
      <ringGeometry args={[2.6,3.25,24]}/>
      <meshBasicMaterial color="#ffffff" depthTest={false}/>
    </mesh>
  </group>)}</>;
}
