import type {BoxMergedCell,BoxOptions} from "./types";
import {initialBox} from "./sample.ts";

export type BoxCell={row:number;col:number;rowspan:number;colspan:number};
export type BoxSelection={row0:number;col0:number;row1:number;col1:number};

export function upgradeBox(saved:Partial<BoxOptions>):BoxOptions {
 const box={...initialBox,...saved};
 // Explicit settings take precedence over 0.5.0's mutually exclusive mode.
 box.sections_enabled=saved.sections_enabled ?? saved.mode==="divided";
 box.lid_type=saved.lid_type ?? (saved.mode==="lid"?"over":"none");
 box.mode="open";
 box.column_weights=(Array.isArray(saved.column_weights)&&saved.column_weights.length===box.columns?
  [...saved.column_weights]:[]);
 box.row_weights=(Array.isArray(saved.row_weights)&&saved.row_weights.length===box.rows?
  [...saved.row_weights]:[]);
 box.merged_cells=Array.isArray(saved.merged_cells)?saved.merged_cells.map(c=>({...c})):[];
 return box;
}

export function axisSizes(weights:number[],count:number,available:number):number[]{
 const real=weights.length===count?weights:Array.from({length:count},()=>1);
 const sum=real.reduce((a,b)=>a+b,0);
 return real.map(value=>available*value/sum);
}
export function interiorDimensions(box:BoxOptions){
 return {
  width:box.width_mm-2*box.wall_mm-box.divider_mm*(box.columns-1),
  depth:box.depth_mm-2*box.wall_mm-box.divider_mm*(box.rows-1)
 };
}
export function columnSizes(box:BoxOptions):number[]{
 return axisSizes(box.column_weights,box.columns,interiorDimensions(box).width);
}
export function rowSizes(box:BoxOptions):number[]{
 return axisSizes(box.row_weights,box.rows,interiorDimensions(box).depth);
}

/** Update a physical mm dimension; resize other cells proportionally.
 * All dimensions remain >=8 mm, and their sum always fills the interior. */
export function resizeAxis(weights:number[],count:number,available:number,
 index:number,requested:number):number[]{
 if(count<=1)return [1];
 const previous=axisSizes(weights,count,available);
 const min=8;
 const target=Math.max(min,Math.min(requested,available-min*(count-1)));
 const remainder=available-target;
 const others=previous.map((x,i)=>i===index?0:Math.max(0,x-min));
 const extra=others.reduce((a,b)=>a+b,0);
 return previous.map((_,i)=>
  i===index?target:min+(remainder-min*(count-1))*(extra?others[i]/extra:1/(count-1)));
}
export function listCells(rows:number,columns:number,merged:BoxMergedCell[]):BoxCell[]{
 const covered=new Set<string>();
 const cells:BoxCell[]=[];
 for(const merge of merged){
  cells.push({...merge});
  for(let row=merge.row;row<merge.row+merge.rowspan;row++)
   for(let col=merge.col;col<merge.col+merge.colspan;col++)
    covered.add(row+":"+col);
 }
 for(let row=0;row<rows;row++)
  for(let col=0;col<columns;col++)
   if(!covered.has(row+":"+col))cells.push({row,col,rowspan:1,colspan:1});
 return cells.sort((a,b)=>a.row-b.row||a.col-b.col);
}

export function selectionFromCell(cell:BoxCell):BoxSelection {
 return {row0:cell.row,col0:cell.col,row1:cell.row+cell.rowspan-1,col1:cell.col+cell.colspan-1};
}
export function extendSelection(a:BoxSelection,b:BoxSelection):BoxSelection{
 return {row0:Math.min(a.row0,b.row0),col0:Math.min(a.col0,b.col0),
  row1:Math.max(a.row1,b.row1),col1:Math.max(a.col1,b.col1)};
}
export function overlapsSelection(cell:BoxCell,s:BoxSelection):boolean {
 return cell.row<=s.row1 && cell.row+cell.rowspan-1>=s.row0 &&
  cell.col<=s.col1 && cell.col+cell.colspan-1>=s.col0;
}
export function insideSelection(cell:BoxCell,s:BoxSelection):boolean{
 return cell.row>=s.row0 && cell.row+cell.rowspan-1<=s.row1 &&
  cell.col>=s.col0 && cell.col+cell.colspan-1<=s.col1;
}
/** Rectangle closure prevents partial overlap with existing merged sections. */
export function closeSelection(selection:BoxSelection,merged:BoxMergedCell[]):BoxSelection {
 let s={...selection};
 let changed=true;
 while(changed){
  changed=false;
  for(const cell of merged){
   if(!overlapsSelection(cell,s) || insideSelection(cell,s))continue;
   s=extendSelection(s,selectionFromCell(cell));
   changed=true;
  }
 }
 return s;
}
export function mergeSelection(merged:BoxMergedCell[],selection:BoxSelection):BoxMergedCell[]{
 const s=closeSelection(selection,merged);
 const result=merged.filter(cell=>!insideSelection(cell,s));
 const width=s.col1-s.col0+1,height=s.row1-s.row0+1;
 if(width*height>1) result.push({row:s.row0,col:s.col0,rowspan:height,colspan:width});
 return result;
}
export function removeAxisMerges(merges:BoxMergedCell[],axis:"row"|"col",index:number):BoxMergedCell[]{
 const key=axis,span=axis==="row"?"rowspan":"colspan";
 return merges.flatMap(source=>{
  const cell={...source};
  const start=cell[key],end=start+cell[span]-1;
  if(index<start)cell[key]--;
  else if(index<=end)cell[span]--;
  return cell.rowspan*cell.colspan>1?[cell]:[];
 });
}