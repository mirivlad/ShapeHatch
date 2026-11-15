import {useEffect, useState, type KeyboardEvent} from "react";

import {parseDecimalDraft} from "./numericParser";

type NumericFieldProps={
 label:string; value:number; onChange:(value:number)=>void;
 min?:number; max?:number; step?:number;
};

export function NumericField({label,value,onChange,min,max,step=0.1}:NumericFieldProps){
 const [draft,setDraft]=useState(()=>String(value));
 const [focused,setFocused]=useState(false);

 // Changes from dragging a handle or selecting a saved project must still
 // update the input, but never overwrite an unfinished keyboard edit.
 useEffect(()=>{if(!focused)setDraft(String(value));},[value,focused]);

 const clamp=(v:number)=>Math.max(min??-Infinity,Math.min(max??Infinity,v));
 function edit(raw:string){
  setDraft(raw);
  const number=parseDecimalDraft(raw);
  if(number!==null && number===clamp(number))onChange(number);
 }
 function finish(){
  const number=parseDecimalDraft(draft);
  if(number===null){
   // Blank / just "-" / an incomplete fraction: leave the last valid value.
   setDraft(String(value));
  } else {
   const committed=clamp(number);
   setDraft(String(committed));
   if(committed!==value)onChange(committed);
  }
  setFocused(false);
 }
 function keyDown(event:KeyboardEvent<HTMLInputElement>){
  if(event.key==="Enter"){event.currentTarget.blur();return;}
  if(event.key!=="ArrowUp"&&event.key!=="ArrowDown")return;
  event.preventDefault();
  const current=parseDecimalDraft(draft)??value;
  // Keep existing number-field arrow keyboard control without relying on
  // locale-dependent <input type="number"> browser parsing.
  const next=clamp(Number((current+(event.key==="ArrowUp"?step:-step)).toFixed(10)));
  setDraft(String(next));
  if(next!==value)onChange(next);
 }
 return <label className="field"><span>{label}</span>
  <input className="numeric-input" type="text" inputMode="decimal"
   autoComplete="off" spellCheck={false}
   value={draft} onFocus={()=>setFocused(true)}
   onChange={event=>edit(event.target.value)}
   onBlur={finish} onKeyDown={keyDown}/>
 </label>;
}