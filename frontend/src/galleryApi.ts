import type { Project } from "./types";

const KEY_NAME="shapehatch-gallery-recovery-key";
const KEY_FORMAT=/^[a-f0-9]{64}$/i;

export type GallerySummary={
 id:string; name:string; kind:"silhouette"|"plate"|"box"; updatedAt:string;
 contentType?:string;
};

export function getGalleryKey():string {
 const stored=localStorage.getItem(KEY_NAME);
 if(stored&&KEY_FORMAT.test(stored))return stored.toLowerCase();
 const random=crypto.getRandomValues(new Uint8Array(32));
 const key=Array.from(random,byte=>byte.toString(16).padStart(2,"0")).join("");
 localStorage.setItem(KEY_NAME,key);
 return key;
}

export function restoreGalleryKey(key:string):void {
 const normalized=key.trim().toLowerCase();
 if(!KEY_FORMAT.test(normalized))throw new Error("Ключ должен содержать 64 шестнадцатеричных символа.");
 localStorage.setItem(KEY_NAME,normalized);
}

async function api<T>(path:string,method="GET",body?:Project):Promise<T>{
 const res=await fetch("/api/gallery/projects"+path,{
  method,headers:{"X-Gallery-Key":getGalleryKey(),
   ...(body?{"Content-Type":"application/json"}:{})},
  ...(body?{body:JSON.stringify(body)}:{})
 });
 if(!res.ok){
  let detail="";
  try{const response=await res.json();detail=String(response.detail??"");}catch{}
  throw new Error(detail||"Ошибка серверной галереи ("+res.status+").");
 }
 return res.json() as Promise<T>;
}

export const listGalleryProjects=()=>api<GallerySummary[]>("");
export const getGalleryProject=(id:string)=>api<Project>("/"+encodeURIComponent(id));
export const putGalleryProject=(project:Project)=>api<{id:string;updatedAt:string}>(
 "/"+encodeURIComponent(project.id),"PUT",project);
export const deleteGalleryProject=(id:string)=>api<{ok:boolean}>("/"+encodeURIComponent(id),"DELETE");