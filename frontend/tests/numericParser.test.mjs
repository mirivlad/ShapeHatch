import assert from "node:assert/strict";
import {test} from "node:test";
import {parseDecimalDraft} from "../src/numericParser.ts";

test("typing transitional characters never silently inserts zero",()=>{
 for(const draft of ["", "-", "+", ".", ",", "-.", "-,", "  "]){
  assert.equal(parseDecimalDraft(draft),null,draft);
 }
});

test("both keyboard layouts and signed coordinates work",()=>{
 for(const [draft,expected] of [
  ["-15",-15],["-15,5",-15.5],["-15.5",-15.5],
  ["-.5",-0.5],["-,5",-0.5],
  ["1,25",1.25],["1.25",1.25],
  ["0",0],["12.",12],["12,",12],
  ["+3,75",3.75],[" 2,5 ",2.5],
 ]){
  assert.equal(parseDecimalDraft(draft),expected,draft);
 }
});

test("invalid text and non-finite values do not become model values",()=>{
 for(const draft of ["1,2.3","--1","1 2","abc","1e6","Infinity","1,2,3","1.2.3"]){
  assert.equal(parseDecimalDraft(draft),null,draft);
 }
 assert.equal(parseDecimalDraft("9".repeat(500)),null);
});