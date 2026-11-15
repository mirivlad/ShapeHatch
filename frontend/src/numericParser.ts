/**
 * Accept localized decimals and transient edits without turning an empty
 * number input into 0 or rejecting a leading minus sign.
 */
export function parseDecimalDraft(raw:string):number|null {
 const text=raw.trim().replace(",",".");
 if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text))return null;
 const result=Number(text);
 return Number.isFinite(result)?result:null;
}
