import {Box, Grid3X3, Layers3} from "lucide-react";
import {NumericField} from "./NumericField";
import type {BoxOptions} from "./types";

/** Independent box generator controls; common preview/gallery/export live in App. */
export function BoxControls({box,step,onChange}:{
 box:BoxOptions;step:number;
 onChange:<K extends keyof BoxOptions>(key:K,value:BoxOptions[K])=>void;
}){
 const number=<K extends keyof BoxOptions>(key:K,label:string,min:number,max:number,step=0.5)=>
  <NumericField label={label} value={box[key] as number} min={min} max={max}
   step={step} onChange={value=>onChange(key,value as BoxOptions[K])}/>;
 const color=(key:"body_color"|"lid_color",label:string)=>
  <label className="field"><span>{label}</span><div className="color-field">
   <input type="color" value={box[key]} onChange={event=>onChange(key,event.target.value.toUpperCase())}/>
   <span>{box[key]}</span></div></label>;

 if(step===0)return <section className="settings-group box-controls">
  <h3><Box size={18}/> Габариты коробочки</h3>
  <p className="field-hint">Указывайте внешние размеры изделия в миллиметрах. Верх коробки остаётся открытым.</p>
  <div className="field-row">
   {number("width_mm","Ширина, мм",30,300,1)}
   {number("depth_mm","Глубина, мм",30,300,1)}
  </div>
  <div className="field-row">
   {number("height_mm","Высота, мм",12,200,1)}
   {number("corner_radius_mm","Скругление углов, мм",0,Math.min(box.width_mm,box.depth_mm)/2,0.5)}
  </div>
  <div className="field-row">
   {number("wall_mm","Толщина стенки, мм",1.2,8,0.2)}
   {number("bottom_mm","Толщина дна, мм",1.2,Math.min(12,box.height_mm-4),0.2)}
  </div>
  {color("body_color","Цвет коробочки")}
  <p className="field-hint">Дно и стенки — одна замкнутая печатаемая деталь, а не пересекающиеся элементы.</p>
 </section>;

 if(step===1)return <section className="settings-group box-controls">
  <h3><Layers3 size={18}/> Исполнение</h3>
  <label className="field"><span>Вариант коробочки</span>
   <select value={box.mode} onChange={event=>onChange("mode",event.target.value as BoxOptions["mode"])}>
    <option value="open">Открытая коробочка</option>
    <option value="lid">Коробочка со съёмной крышкой</option>
    <option value="divided">Коробочка с отделениями</option>
   </select>
  </label>
  {box.mode==="open"&&<p className="field-hint">Простая открытая коробочка без дополнительных деталей.</p>}
  {box.mode==="lid"&&<>
   <p className="field-hint">Крышка надевается сверху на внешние стенки. На столе для печати она лежит рядом с коробочкой открытой стороной вверх.</p>
   <div className="field-row">
    {number("lid_clearance_mm","Зазор посадки с каждой стороны, мм",0.1,1.2,0.05)}
    {number("lid_wall_mm","Толщина бортика крышки, мм",1.2,8,0.2)}
   </div>
   <div className="field-row">
    {number("lid_top_mm","Толщина крышки, мм",1.2,8,0.2)}
    {number("lid_skirt_mm","Высота бортика, мм",3,20,0.5)}
   </div>
   {color("lid_color","Цвет крышки")}
   <p className="field-hint">Для начала попробуйте 0,3 мм зазора на сторону, затем скорректируйте под свой пластик и принтер.</p>
  </>}
  {box.mode==="divided"&&<>
   <p className="field-hint">Перегородки печатаются вместе с корпусом. Количество отделений задаётся по ширине и глубине.</p>
   <div className="field-row">
    {number("columns","Отделений по ширине",1,6,1)}
    {number("rows","Отделений по глубине",1,6,1)}
   </div>
   {number("divider_mm","Толщина перегородок, мм",1.2,8,0.2)}
   <p className="field-hint"><Grid3X3 size={14}/> Все отделения должны быть не меньше 8 × 8 мм. Если размеры не подходят, редактор покажет причину.</p>
  </>}
 </section>;

 return null;
}