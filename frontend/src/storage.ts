import type { Project } from "./types";
const DATABASE = "shapehatch-projects", STORE = "projects";
function openDatabase(): Promise<IDBDatabase> {
 return new Promise((resolve,reject)=>{
  const request=indexedDB.open(DATABASE,1);
  request.onupgradeneeded=()=>request.result.createObjectStore(STORE,{keyPath:"id"});
  request.onsuccess=()=>resolve(request.result);
  request.onerror=()=>reject(request.error);
 });
}
async function query<T>(makeRequest:(store:IDBObjectStore)=>IDBRequest<T>,mode:IDBTransactionMode="readonly"):Promise<T> {
 const db=await openDatabase();
 return new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,mode);
  const req=makeRequest(tx.objectStore(STORE));
  req.onsuccess=()=>resolve(req.result);
  req.onerror=()=>reject(req.error);
  tx.oncomplete=()=>db.close();
  tx.onerror=()=>{db.close();reject(tx.error);};
 });
}
export const getProjects=()=>query<Project[]>(store=>store.getAll()).then(items=>items.sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)));
export const saveProject=(project:Project)=>query<IDBValidKey>(store=>store.put(project),"readwrite");
export const removeProject=(id:string)=>query<undefined>(store=>store.delete(id),"readwrite");
