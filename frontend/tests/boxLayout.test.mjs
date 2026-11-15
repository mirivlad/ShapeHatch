import test from "node:test";
import assert from "node:assert/strict";
import {
 upgradeBox,axisSizes,interiorDimensions,columnSizes,rowSizes,resizeAxis,
 listCells,selectionFromCell,extendSelection,closeSelection,mergeSelection,
 removeAxisMerges
} from "../src/boxLayout.ts";

test("version 0.5.0 boxes automatically recover their former modes",()=>{
 assert.equal(upgradeBox({mode:"open"}).sections_enabled,false);
 assert.equal(upgradeBox({mode:"open"}).lid_type,"none");
 assert.equal(upgradeBox({mode:"lid"}).lid_type,"over");
 assert.equal(upgradeBox({mode:"divided",rows:3,columns:4}).sections_enabled,true);
 const legacy=upgradeBox({mode:"lid",sections_enabled:true,lid_type:"inset"});
 assert.equal(legacy.sections_enabled,true);
 assert.equal(legacy.lid_type,"inset");
 assert.equal(legacy.mode,"open");
});

test("editing one section's mm dimension preserves the interior sum and >=8 mm",()=>{
 const box=upgradeBox({sections_enabled:true,columns:3,rows:2});
 const {width,depth}=interiorDimensions(box);
 const initial=columnSizes(box);
 const target=55.1;
 const weights=resizeAxis(box.column_weights,box.columns,width,0,target);
 const sizes=axisSizes(weights,3,width);
 assert.ok(sizes.every(n=>n>=8));
 assert.ok(Math.abs(sizes[0]-target)<1e-8);
 assert.ok(Math.abs(sizes.reduce((a,b)=>a+b,0)-width)<1e-8);
 assert.ok(initial[0]<sizes[0]);
 const tiny=resizeAxis(weights,3,width,0,10000);
 assert.ok(axisSizes(tiny,3,width).slice(1).every(n=>n>=8));
 assert.ok(Math.abs(rowSizes(box).reduce((a,b)=>a+b,0)-depth)<1e-8);
});

test("one wide compartment and three narrow compartments can be represented",()=>{
 const merged=[{row:0,col:0,rowspan:1,colspan:3}];
 const cells=listCells(2,3,merged);
 assert.equal(cells.length,4);
 assert.deepEqual(cells[0],{row:0,col:0,rowspan:1,colspan:3});
 assert.equal(cells.filter(c=>c.row===1).length,3);
});

test("shift selection merges contiguous cells and can be split again",()=>{
 const a=selectionFromCell({row:0,col:0,rowspan:1,colspan:1});
 const b=selectionFromCell({row:1,col:2,rowspan:1,colspan:1});
 const selection=extendSelection(a,b);
 const merged=mergeSelection([],selection);
 assert.deepEqual(merged,[{row:0,col:0,rowspan:2,colspan:3}]);
 assert.equal(listCells(2,3,merged).length,1);
 assert.equal(listCells(2,3,[]).length,6);
});

test("selecting a piece of merged cell expands to whole rectangle",()=>{
 const prior=[{row:0,col:0,rowspan:1,colspan:3}];
 const selection={row0:0,col0:2,row1:1,col1:2};
 const closed=closeSelection(selection,prior);
 assert.deepEqual(closed,{row0:0,col0:0,row1:1,col1:2});
 assert.deepEqual(mergeSelection(prior,selection),[{row:0,col:0,rowspan:2,colspan:3}]);
});

test("removing a row or column repairs merge coordinates and spans",()=>{
 const merged=[{row:0,col:0,rowspan:2,colspan:3}];
 assert.deepEqual(removeAxisMerges(merged,"col",2),[{row:0,col:0,rowspan:2,colspan:2}]);
 assert.deepEqual(removeAxisMerges(merged,"row",1),[{row:0,col:0,rowspan:1,colspan:3}]);
 assert.deepEqual(removeAxisMerges([{row:0,col:0,rowspan:1,colspan:2}],"col",1),[]);
});