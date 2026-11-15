import {useRef,useState,type PointerEvent as ReactPointerEvent} from "react";
import {Box,Grid3X3,Layers3,Plus,Minus,Combine,Split} from "lucide-react";
import {NumericField} from "./NumericField";
import {columnSizes,rowSizes,interiorDimensions,resizeAxis,listCells,
 closeSelection,selectionFromCell,extendSelection,mergeSelection,
 insideSelection,removeAxisMerges,type BoxSelection,type BoxCell} from "./boxLayout";
import type {BoxOptions} from "./types";

/** Shared box wizard: body, flexible sections, independent lid, export. */
export function BoxControls({box,step,onChange}:{
 box:BoxOptions;step:number;
 onChange:<K extends keyof BoxOptions>(key:K,value:BoxOptions[K])=>void;
}){
 const [selection,setSelection]=useState<BoxSelection|null>(null);
 const gridRef=useRef<HTMLDivElement|null>(null);
 const dragRef=useRef<{
  axis:"col"|"row";index:number;start:number;value:number;available:number;
  weights:number[];count:number;pixels:number
 }|null>(null);
 const [anchor,setAnchor]=useState<BoxSelection|null>(null);
 const number=<K extends keyof BoxOptions>(key:K,label:string,min:number,max:number,inc=0.5)=>
  <NumericField label={label} value={box[key] as number} min={min} max={max}
   step={inc} onChange={value=>onChange(key,value as BoxOptions[K])}/>;
 const color=(key:"body_color"|"lid_color",label:string)=>
  <label className="field"><span>{label}</span><div className="color-field">
   <input type="color" value={box[key]} onChange={event=>onChange(key,event.target.value.toUpperCase())}/>
   <span>{box[key]}</span></div></label>;

 const changeCount=(axis:"row"|"col",delta:number)=>{
  const countKey=axis==="col"?"columns":"rows";
  const weightKey=axis==="col"?"column_weights":"row_weights";
  const count=box[countKey],next=count+delta;
  if(next<1||next>6)return;
  const oldWeights=box[weightKey].length===count?box[weightKey]:Array(count).fill(1);
  const weights=delta>0?[...oldWeights,oldWeights.reduce((a,b)=>a+b,0)/count]:
   oldWeights.slice(0,-1);
  onChange(countKey,next);
  onChange(weightKey,weights);
  if(delta<0)onChange("merged_cells",removeAxisMerges(box.merged_cells,axis,count-1));
  setSelection(null);setAnchor(null);
 };
 const setAxisSize=(axis:"row"|"col",index:number,value:number)=>{
  const {width,depth}=interiorDimensions(box);
  if(axis==="col")onChange("column_weights",
   resizeAxis(box.column_weights,box.columns,width,index,value));
  else onChange("row_weights",
   resizeAxis(box.row_weights,box.rows,depth,index,value));
 };
 const widths=columnSizes(box),depths=rowSizes(box);
 const beginDrag=(event:ReactPointerEvent<HTMLButtonElement>,axis:"col"|"row",index:number)=>{
  const rect=gridRef.current?.getBoundingClientRect();
  if(!rect)return;
  event.stopPropagation();event.preventDefault();
  const available=axis==="col"?interiorDimensions(box).width:interiorDimensions(box).depth;
  const sizes=axis==="col"?widths:depths;
  dragRef.current={axis,index,start:axis==="col"?event.clientX:event.clientY,
   value:sizes[index],available,weights:[...sizes],count:sizes.length,
   pixels:Math.max(1,axis==="col"?rect.width-18:rect.height-18)};
  event.currentTarget.setPointerCapture(event.pointerId);
 };
 const moveDrag=(event:ReactPointerEvent<HTMLButtonElement>)=>{
  if(!dragRef.current)return;
  event.stopPropagation();
  const {axis,index,start,value,available,weights,count,pixels}=dragRef.current;
  const current=axis==="col"?event.clientX:event.clientY;
  const mm=value+(current-start)*available/pixels;
  const newWeights=resizeAxis(weights,count,available,index,mm);
  if(axis==="col")onChange("column_weights",newWeights);
  else onChange("row_weights",newWeights);
 };
 const finishDrag=(event:ReactPointerEvent<HTMLButtonElement>)=>{
  if(dragRef.current){event.stopPropagation();dragRef.current=null;}
  if(event.currentTarget.hasPointerCapture(event.pointerId))
   event.currentTarget.releasePointerCapture(event.pointerId);
 };
 const cells=listCells(box.rows,box.columns,box.merged_cells);
 const selected=selection?closeSelection(selection,box.merged_cells):null;
 const selectCell=(cell:BoxCell,shift:boolean)=>{
  const next=selectionFromCell(cell);
  if(shift&&anchor){
   setSelection(closeSelection(extendSelection(anchor,next),box.merged_cells));
  }else{
   setSelection(next);
   setAnchor(next);
  }
 };
 const selectedMerge=selected?box.merged_cells.find(cell=>
  insideSelection(cell,selected)&&cell.row===selected.row0&&cell.col===selected.col0&&
  cell.row+cell.rowspan-1===selected.row1&&cell.col+cell.colspan-1===selected.col1):undefined;

 if(step===0)return <section className="settings-group box-controls">
  <h3><Box size={18}/> Габариты коробочки</h3>
  <p className="field-hint">Внешние размеры изделия в миллиметрах. Дно и стенки печатаются одной деталью.</p>
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
   {number("bottom_mm","Толщина дна, мм",1.2,Math.max(1.2,Math.min(12,box.height_mm-4)),0.2)}
  </div>
  {color("body_color","Цвет коробочки")}
 </section>;

 if(step===1)return <section className="settings-group box-controls">
  <h3><Grid3X3 size={18}/> Секции и перегородки</h3>
  <label className="toggle"><span>Добавить внутренние секции</span>
   <input type="checkbox" checked={box.sections_enabled}
    onChange={event=>onChange("sections_enabled",event.target.checked)}/>
  </label>
  {!box.sections_enabled?<p className="field-hint">Коробочка будет с одной общей полостью. Крышку можно настроить отдельно на следующем шаге.</p>:<>
   <p className="field-hint">Это схема вида сверху. Перетаскивайте линии перегородок мышью, либо выберите ячейку и затем Shift + щелчок по другой, чтобы выделить прямоугольную область для объединения.</p>
   <div className="box-grid-toolbar">
    <button type="button" onClick={()=>changeCount("col",-1)} disabled={box.columns<=1} aria-label="Убрать последний столбец"><Minus size={15}/></button>
    <span>Столбцов: {box.columns}</span>
    <button type="button" onClick={()=>changeCount("col",1)} disabled={box.columns>=6} aria-label="Добавить столбец"><Plus size={15}/></button>
    <button type="button" onClick={()=>changeCount("row",-1)} disabled={box.rows<=1} aria-label="Убрать последнюю строку"><Minus size={15}/></button>
    <span>Строк: {box.rows}</span>
    <button type="button" onClick={()=>changeCount("row",1)} disabled={box.rows>=6} aria-label="Добавить строку"><Plus size={15}/></button>
   </div>
   <div ref={gridRef} className="box-grid-visual" role="group" aria-label="Схема секций коробочки"
    style={{gridTemplateColumns:widths.map(w=>Math.max(1,w)+"fr").join(" "),
     gridTemplateRows:depths.map(h=>Math.max(1,h)+"fr").join(" ")}}>
    {cells.map((cell,index)=>{
     const active=selected&&insideSelection(cell,selected);
     const w=widths.slice(cell.col,cell.col+cell.colspan).reduce((a,b)=>a+b,0)+box.divider_mm*(cell.colspan-1);
     const h=depths.slice(cell.row,cell.row+cell.rowspan).reduce((a,b)=>a+b,0)+box.divider_mm*(cell.rowspan-1);
     return <button type="button" key={cell.row+":"+cell.col}
      className={"box-grid-cell"+(active?" selected":"")}
      onClick={event=>selectCell(cell,event.shiftKey)}
      style={{gridColumn:(cell.col+1)+" / span "+cell.colspan,
       gridRow:(cell.row+1)+" / span "+cell.rowspan}}
      title={`Секция ${index+1}: ${w.toFixed(1)} × ${h.toFixed(1)} мм`}>
      <strong>{index+1}</strong><span>{w.toFixed(1)} × {h.toFixed(1)}</span>
     </button>;
    })}
    {widths.slice(0,-1).map((_,index)=>{
     const pct=widths.slice(0,index+1).reduce((a,b)=>a+b,0)/widths.reduce((a,b)=>a+b,0)*100;
     return <button key={"handle-col-"+index} type="button" className="box-grid-divider vertical"
      style={{left:pct+"%"}} aria-label={`Переместить вертикальную перегородку ${index+1}`}
      onPointerDown={event=>beginDrag(event,"col",index)} onPointerMove={moveDrag}
      onPointerUp={finishDrag} onPointerCancel={finishDrag}
      onKeyDown={event=>{if(event.key==="ArrowLeft"||event.key==="ArrowRight"){
       event.preventDefault();setAxisSize("col",index,widths[index]+(event.key==="ArrowRight"?1:-1));
      }}}/>;
    })}
    {depths.slice(0,-1).map((_,index)=>{
     const pct=depths.slice(0,index+1).reduce((a,b)=>a+b,0)/depths.reduce((a,b)=>a+b,0)*100;
     return <button key={"handle-row-"+index} type="button" className="box-grid-divider horizontal"
      style={{top:pct+"%"}} aria-label={`Переместить горизонтальную перегородку ${index+1}`}
      onPointerDown={event=>beginDrag(event,"row",index)} onPointerMove={moveDrag}
      onPointerUp={finishDrag} onPointerCancel={finishDrag}
      onKeyDown={event=>{if(event.key==="ArrowUp"||event.key==="ArrowDown"){
       event.preventDefault();setAxisSize("row",index,depths[index]+(event.key==="ArrowDown"?1:-1));
      }}}/>;
    })}
   </div>
   <div className="box-grid-actions">
    <button type="button" disabled={!selected||((selected.col1-selected.col0+1)*(selected.row1-selected.row0+1)<=1)}
     onClick={()=>{if(selected){onChange("merged_cells",mergeSelection(box.merged_cells,selected));setSelection(selected);setAnchor(selected);}}}>
     <Combine size={15}/> Объединить
    </button>
    <button type="button" disabled={!selectedMerge}
     onClick={()=>{if(selectedMerge){onChange("merged_cells",box.merged_cells.filter(x=>x!==selectedMerge));setSelection(null);setAnchor(null);}}}>
     <Split size={15}/> Разделить
    </button>
   </div>
   <button type="button" className="box-grid-preset" onClick={()=>{
    onChange("columns",3);onChange("rows",2);onChange("column_weights",[1,1,1]);
    onChange("row_weights",[1,1]);onChange("merged_cells",[{row:0,col:0,rowspan:1,colspan:3}]);
    setSelection(null);setAnchor(null);
   }}>Пример: одна широкая секция + три узких</button>
   <p className="field-hint">Точные размеры каждой колонки и строки задаются ниже. При изменении одной ширины соседние перераспределяются; при изменении размера корпуса пропорции сохраняются.</p>
   <div className="box-size-editor">
    <strong>Ширина колонок</strong>
    {widths.map((w,index)=><NumericField key={"width"+index} label={`Колонка ${index+1}, мм`}
     value={Number(w.toFixed(2))} min={8}
     max={Math.max(8,interiorDimensions(box).width-8*(box.columns-1))}
     step={0.5} onChange={value=>setAxisSize("col",index,value)}/>)}
    <strong>Глубина строк</strong>
    {depths.map((h,index)=><NumericField key={"depth"+index} label={`Строка ${index+1}, мм`}
     value={Number(h.toFixed(2))} min={8}
     max={Math.max(8,interiorDimensions(box).depth-8*(box.rows-1))}
     step={0.5} onChange={value=>setAxisSize("row",index,value)}/>)}
   </div>
   {number("divider_mm","Толщина перегородок, мм",1.2,8,0.2)}
   <p className="field-hint">Секции и перегородки составляют единую цельную печатаемую коробочку. Минимальная ширина секции — 8 мм.</p>
  </>}
 </section>;

 if(step===2)return <section className="settings-group box-controls">
  <h3><Layers3 size={18}/> Крышка</h3>
  <label className="field"><span>Тип крышки</span>
   <select value={box.lid_type} onChange={event=>onChange("lid_type",event.target.value as BoxOptions["lid_type"])}>
    <option value="none">Без крышки</option>
    <option value="over">Накладная — на внешние стенки</option>
    <option value="inset">Вставная — бортик внутрь коробочки</option>
   </select>
  </label>
  {box.lid_type==="none"?<p className="field-hint">Коробочка остаётся открытой, независимо от количества секций.</p>:<>
   <p className="field-hint">{box.lid_type==="over"?
    "Крышка надевается на корпус снаружи. Зазор задаётся между внешней стенкой и бортиком крышки.":
    "Верхняя пластина опирается на края коробки, а бортик входит внутрь на выбранную глубину. Это не шарнир."}</p>
   <div className="field-row">
    {number("lid_clearance_mm","Зазор с каждой стороны, мм",0.1,1.2,0.05)}
    {number("lid_wall_mm","Толщина бортика, мм",1.2,8,0.2)}
   </div>
   <div className="field-row">
    {number("lid_top_mm","Толщина верхней пластины, мм",1.2,8,0.2)}
    {number("lid_skirt_mm",box.lid_type==="inset"?"Глубина вставки, мм":"Глубина надевания, мм",
     3,Math.max(3,Math.min(20,box.height_mm-box.bottom_mm-0.1)),0.5)}
   </div>
   {color("lid_color","Цвет крышки")}
   <p className="field-hint">Крышка экспортируется отдельной цельной деталью рядом с коробкой, внешней стороной вниз. После печати её нужно перевернуть. Рекомендуемый начальный зазор — 0,3 мм с каждой стороны.</p>
  </>}
 </section>;

 return null;
}