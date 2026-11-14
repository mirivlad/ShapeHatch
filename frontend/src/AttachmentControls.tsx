import {Plus,Trash2} from "lucide-react";
import type {MagnetSettings,MountType} from "./types";

const modes:{value:MountType;label:string}[]=[
 {value:"none",label:"Без крепления"},
 {value:"loop",label:"Петелька в плоскости"},
 {value:"hole",label:"Сквозное отверстие"},
 {value:"upright",label:"Столбик с поперечным отверстием"},
 {value:"magnets",label:"Посадочные места под магниты"}
];
function NumberField({label,value,min,max,step=0.1,onChange}:{
 label:string;value:number;min:number;max:number;step?:number;onChange:(v:number)=>void
}){
 return <label className="field"><span>{label}</span><input type="number"
  min={min} max={max} step={step} value={value}
  onChange={e=>{const v=Number(e.target.value);if(Number.isFinite(v))onChange(v);}}/></label>;
}
export function AttachmentControls({type,onTypeChange,hole,wall,onHole,onWall,magnets,onMagnets}:{
 type:MountType;onTypeChange:(v:MountType)=>void;
 hole:number;wall:number;onHole:(v:number)=>void;onWall:(v:number)=>void;
 magnets:MagnetSettings;onMagnets:(v:MagnetSettings)=>void
}){
 const patch=<K extends keyof MagnetSettings>(key:K,value:MagnetSettings[K])=>
   onMagnets({...magnets,[key]:value});
 const add=()=>{
  if(magnets.positions.length>=8)return;
  const step=Math.max(9,magnets.shape==="round"?magnets.diameter_mm+4:magnets.width_mm+4);
  const n=magnets.positions.length;
  onMagnets({...magnets,positions:[...magnets.positions,
   {x_mm:Number((n%2===0?(n+1)*step/2:-(n+1)*step/2).toFixed(1)),y_mm:0}]});
 };
 const changePoint=(index:number,axis:"x_mm"|"y_mm",value:number)=>{
  patch("positions",magnets.positions.map((p,i)=>i===index?{...p,[axis]:value}:p));
 };
 return <div className="attachment-controls">
  <label className="field"><span>Тип крепления</span>
   <select value={type} onChange={e=>onTypeChange(e.target.value as MountType)}>
    {modes.map(item=><option key={item.value} value={item.value}>{item.label}</option>)}
   </select>
  </label>
  {["hole","loop","upright"].includes(type)&&<div className="field-row">
   <NumberField label="Диаметр отверстия, мм" value={hole} min={2} max={12} onChange={onHole}/>
   <NumberField label="Толщина стенки, мм" value={wall} min={1} max={6} onChange={onWall}/>
  </div>}
  {type==="magnets"&&<>
   <div className="field-row">
    <label className="field"><span>Форма магнита</span>
     <select value={magnets.shape} onChange={e=>patch("shape",e.target.value as MagnetSettings["shape"])}>
      <option value="round">Круглый</option><option value="rectangle">Прямоугольный</option>
     </select>
    </label>
    <NumberField label="Глубина кармана, мм" value={magnets.depth_mm} min={0.5}
     max={10} onChange={v=>patch("depth_mm",v)}/>
   </div>
   <div className="field-row">
    {magnets.shape==="round"?<NumberField label="Диаметр магнита, мм"
     value={magnets.diameter_mm} min={2} max={30} onChange={v=>patch("diameter_mm",v)}/>:<>
     <NumberField label="Ширина магнита, мм" value={magnets.width_mm} min={2} max={50}
       onChange={v=>patch("width_mm",v)}/>
     <NumberField label="Длина магнита, мм" value={magnets.height_mm} min={2} max={50}
       onChange={v=>patch("height_mm",v)}/>
    </>}
    <NumberField label="Допуск на посадку, мм" value={magnets.clearance_mm}
      min={0} max={1} step={0.05} onChange={v=>patch("clearance_mm",v)}/>
   </div>
   <div className="magnet-list-header">
    <strong>Посадочные места ({magnets.positions.length}/8)</strong>
    <button type="button" disabled={magnets.positions.length>=8} onClick={add}>
     <Plus size={14}/> Добавить
    </button>
   </div>
   {magnets.positions.map((point,index)=><div className="magnet-position-row" key={index}>
    <span>#{index+1}</span>
    <NumberField label="X, мм" value={point.x_mm} min={-150} max={150}
      onChange={v=>changePoint(index,"x_mm",v)}/>
    <NumberField label="Y, мм" value={point.y_mm} min={-150} max={150}
      onChange={v=>changePoint(index,"y_mm",v)}/>
    <button className="remove-magnet" title="Удалить" aria-label={"Удалить магнит "+(index+1)}
     onClick={()=>patch("positions",magnets.positions.filter((_,i)=>index!==i))}>
     <Trash2 size={16}/></button>
   </div>)}
   <small className="field-hint">Сиреневые маркеры на 3D-модели перемещают карманы. Магниты вставляются после печати.</small>
  </>}
 </div>;
}
