import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  Box, Check, ChevronDown, ChevronLeft, CircleHelp, Download, FileImage, FolderOpen, ImagePlus,
  Layers3, LoaderCircle, Plus, RotateCcw, Save, Settings2, Shapes, Trash2,
  Type, UploadCloud, X, ZoomIn,
  type LucideIcon
} from "lucide-react";
import { Viewer, type CameraView } from "./Viewer";
import { goatDataUrl, initialPicture, initialPlate, initialSilhouette } from "./sample";
import { AttachmentControls } from "./AttachmentControls";
import { getProjects, removeProject, saveProject } from "./storage";
import { loadMountPreferences, storeMountPreferences } from "./mountPreferences";
import type { InnerContourSetting, Plate, Preview, Project, Section, Silhouette,
 MagnetSettings, MountType, PicturePreview, PictureSettings } from "./types";

function NumberInput({ label, value, onChange, min, max, step=0.1 }: {
  label:string; value:number; onChange:(value:number)=>void; min?:number; max?:number; step?:number
}) {
  return <label className="field"><span>{label}</span>
    <input type="number" value={value} min={min} max={max} step={step}
      onChange={e=>{const n=Number(e.target.value);if(Number.isFinite(n))onChange(n);}}/>
  </label>;
}
function OptionSelect({label,value,options,onChange}:{
 label:string; value:string; options:{value:string;label:string}[]; onChange:(v:string)=>void
}) {
 return <label className="field"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}>
  {options.map(o=><option value={o.value} key={o.value}>{o.label}</option>)}
 </select></label>;
}
function Toggle({label,checked,onChange}:{label:string;checked:boolean;onChange:(v:boolean)=>void}) {
 return <label className="toggle"><span>{label}</span>
  <input type="checkbox" checked={checked} onChange={e=>onChange(e.target.checked)}/>
 </label>;
}
function ColorInput({label,value,onChange}:{label:string;value:string;onChange:(v:string)=>void}) {
 return <label className="field"><span>{label}</span><div className="color-field">
  <input type="color" value={value} onChange={e=>onChange(e.target.value.toUpperCase())}/>
  <span>{value}</span></div></label>;
}

function Accordion({title,icon:Icon,opened,onToggle,children}:{
 title:string;icon:LucideIcon;opened:boolean;onToggle:()=>void;children:ReactNode
}) {
 return <section className={"settings-group accordion"+(opened?" expanded":"")}>
  <h3><button type="button" className="accordion-header" aria-expanded={opened}
    onClick={onToggle}><Icon size={18}/><span>{title}</span>
    <ChevronDown size={17} className="accordion-arrow"/></button></h3>
  {opened&&<div className="accordion-body">{children}</div>}
 </section>;
}

const views:{id:CameraView;label:string}[]=[
 {id:"iso",label:"3D"},{id:"top",label:"Сверху"},{id:"front",label:"Спереди"},
 {id:"left",label:"Слева"},{id:"right",label:"Справа"},{id:"bottom",label:"Снизу"}];

export function App() {
 const [section,setSection]=useState<Section>("home");
 const [mountPrefs,setMountPrefs]=useState(loadMountPreferences);
 const [silhouette,setSilhouette]=useState<Silhouette>(()=>({
  ...initialSilhouette,loop_hole_mm:mountPrefs.holeMm,loop_wall_mm:mountPrefs.wallMm
 }));
 const [plate,setPlate]=useState<Plate>(()=>({
  ...initialPlate,mount_hole_mm:mountPrefs.holeMm,mount_wall_mm:mountPrefs.wallMm
 }));
 const [openGroup,setOpenGroup]=useState("image");
 const [editorStep,setEditorStep]=useState(0);
 const [picturePreview,setPicturePreview]=useState<PicturePreview|null>(null);
 const [pictureError,setPictureError]=useState("");
 const [pictureBusy,setPictureBusy]=useState(false);
 const [selectedContour,setSelectedContour]=useState<string|null>(null);
 const toggleGroup=(id:string)=>setOpenGroup(old=>old===id?"":id);
 const [model,setModel]=useState<Preview|null>(null);
 const [view,setView]=useState<CameraView>("iso");
 const [busy,setBusy]=useState(false);
 const [exporting,setExporting]=useState<string|null>(null);
 const [error,setError]=useState("");
 const [toast,setToast]=useState("");
 const [projects,setProjects]=useState<Project[]>([]);
 const [galleryFilter,setGalleryFilter]=useState<"all"|"silhouette"|"plate">("all");
 const [projectId,setProjectId]=useState<string|null>(null);
 const [projectName,setProjectName]=useState("");
 const changeSilhouette=<K extends keyof Silhouette>(key:K,value:Silhouette[K])=>{
  setSilhouette(prev=>({...prev,[key]:value}));
  if(key==="loop_hole_mm"||key==="loop_wall_mm")
   setMountPrefs(prev=>({...prev,[key==="loop_hole_mm"?"holeMm":"wallMm"]:Number(value)}));
 };
 const changeInner=(id:string, values:Partial<InnerContourSetting>)=>{
  setSilhouette(prev=>{
   const old=prev.inner_contours??[];
   const original=old.find(item=>item.id===id)??{
    id,fill:prev.mode==="cutouts"?"empty":"same",color:"#F26C50"
   };
   const updated={...original,...values} as InnerContourSetting;
   return {...prev,inner_contours:[...old.filter(item=>item.id!==id),updated]};
  });
 };
 const selectContour=(id:string)=>{setSelectedContour(id);setEditorStep(1);setOpenGroup("contours");};
 const changePlate=<K extends keyof Plate>(key:K,value:Plate[K])=>{
  setPlate(prev=>({...prev,[key]:value}));
  if(key==="content_type")setModel(null);
  if(key==="mount_hole_mm"||key==="mount_wall_mm")
   setMountPrefs(prev=>({...prev,[key==="mount_hole_mm"?"holeMm":"wallMm"]:Number(value)}));
 };
 useEffect(()=>storeMountPreferences(mountPrefs),[mountPrefs]);
 const changePicture=<K extends keyof PictureSettings>(key:K,value:PictureSettings[K])=>
  setPlate(prev=>({...prev,picture:{...prev.picture,[key]:value}}));
 const updateMagnet=(index:number,x:number,y:number)=>{
  const move=(current:MagnetSettings)=>({...current,positions:current.positions.map((p,i)=>i===index?{x_mm:x,y_mm:y}:p)});
  if(section==="silhouette")setSilhouette(prev=>({...prev,magnets:move(prev.magnets)}));
  else setPlate(prev=>({...prev,magnets:move(prev.magnets)}));
 };
 const silhouetteMount:MountType=silhouette.mount_type??(
  silhouette.attach_loop?(silhouette.loop_orientation==="upright"?"upright":"loop"):"none");
 const currentMount:MountType=section==="silhouette"?silhouetteMount:plate.mount_type;
 const pictureMode=section==="plate"&&plate.content_type==="image";
 const wizardSteps=section==="silhouette"
  ?["Силуэт","Внутренние контуры","Размеры","Крепление","Экспорт"]
  :pictureMode
  ?["Содержимое","Основа","Картинка и масштаб","Оптимизация цветов","Крепление","Экспорт"]
  :["Содержимое","Текст","Основа и размещение","Крепление","Экспорт"];
 const mountStep=pictureMode?4:3;
 const groupFor=(step:number):string=>section==="silhouette"
  ?["image","contours","dimensions","loop","export"][step]
  :pictureMode
  ?["content","base","picture","colors","mount","export"][step]
  :["content","text","base","mount","export"][step];
 const goStep=(step:number)=>{
  const next=Math.max(0,Math.min(wizardSteps.length-1,step));
  setEditorStep(next);setOpenGroup(groupFor(next));
  if(next===mountStep && currentMount==="magnets")setView(
   pictureMode?"top":"bottom");
  if(pictureMode&&(next===1||next===2))setView("bottom");
 };
 const pictureProcessingKey=JSON.stringify([
  plate.picture.image_data,plate.picture.algorithm,plate.picture.image_kind,
  plate.picture.dithering,plate.picture.color_count,plate.picture.resolution,
  plate.picture.filament_palette,plate.picture.color_overrides
 ]);
 useEffect(()=>{
  if(section!=="plate"||plate.content_type!=="image"||!plate.picture.image_data){
   setPicturePreview(null);setPictureError("");setPictureBusy(false);return;
  }
  const controller=new AbortController();
  setPictureBusy(true);setPictureError("");setPicturePreview(null);
  const timeout=setTimeout(async()=>{
   try{
    const response=await fetch("/api/picture/preview",{
     method:"POST",headers:{"Content-Type":"application/json"},
     body:JSON.stringify(plate.picture),signal:controller.signal
    });
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||"Не удалось оптимизировать изображение.");
    if(!controller.signal.aborted)setPicturePreview(data as PicturePreview);
   }catch(e){if(!controller.signal.aborted)setPictureError(e instanceof Error?e.message:String(e));}
   finally{if(!controller.signal.aborted)setPictureBusy(false);}
  },250);
  return ()=>{clearTimeout(timeout);controller.abort();};
 },[section,plate.content_type,pictureProcessingKey]);

 const isEditor=section==="silhouette"||section==="plate";
 const visibleProjects=projects.filter(p=>galleryFilter==="all"||p.kind===galleryFilter);
 const kind=section==="plate"?"plate":"silhouette";
 const request=useCallback(()=> section==="plate"
  ?{kind:"plate",plate}
  :{kind:"silhouette",silhouette},[section,plate,silhouette]);

 useEffect(()=>{
  if(!isEditor) return;
  const abort=new AbortController();
  setBusy(true);setError("");
  const timeout=setTimeout(async()=>{
   try {
    const response=await fetch("/api/preview",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(request()),signal:abort.signal});
    const body=await response.json();
    if(!response.ok) throw new Error(typeof body.detail==="string"?body.detail:"Не удалось создать модель.");
    setModel(body as Preview);
   } catch(ex) {
    if(!abort.signal.aborted) {
     // Keep the last good mesh and drag controls visible so invalid text can
     // be moved back inside the plate; exporting remains disabled on error.
     setError(ex instanceof Error?ex.message:String(ex));
    }
   } finally {if(!abort.signal.aborted)setBusy(false);}
  },480);
  return ()=>{clearTimeout(timeout);abort.abort();};
 },[isEditor,request]);

 async function refreshGallery() {
  try {setProjects(await getProjects());}
  catch {setToast("Не удалось открыть локальную галерею.");}
 }
 function navigate(next:Section) {
  setSection(next);setModel(null);setError("");setEditorStep(0);
  if(next==="plate"||next==="silhouette")setOpenGroup(next==="plate"?"content":"image");
  if(next==="gallery")void refreshGallery();
 }
 function create(next:"silhouette"|"plate") {
  setSelectedContour(null);
  setProjectId(null);
  setProjectName("");
  setSilhouette({...initialSilhouette,loop_hole_mm:mountPrefs.holeMm,loop_wall_mm:mountPrefs.wallMm});
  setPlate({...initialPlate,mount_hole_mm:mountPrefs.holeMm,mount_wall_mm:mountPrefs.wallMm});
  setView("iso");
  navigate(next);
 }
 async function upload(file:File) {
  if(file.size>5_000_000){setError("Файл больше 5 МБ.");return;}
  const format=file.type || ({svg:"image/svg+xml",jpg:"image/jpeg",jpeg:"image/jpeg",
    png:"image/png",webp:"image/webp"}[file.name.split(".").pop()?.toLowerCase()??""]||"");
  if(!["image/svg+xml","image/jpeg","image/png","image/webp"].includes(format)){
    setError("Поддерживаются PNG, JPG, WebP и SVG.");return;}
  const reader=new FileReader();
  reader.onload=()=>{if(typeof reader.result==="string"){
   setSilhouette(prev=>({...prev,image_data:reader.result as string,filename:file.name,inner_contours:[]}));
   setSelectedContour(null);}};
  reader.onerror=()=>setError("Не удалось прочитать файл.");
  reader.readAsDataURL(file.type === format ? file : new Blob([file], {type: format}));
 }
 async function uploadPicture(file:File){
  if(file.size>5_000_000){setPictureError("Максимальный размер файла 5 МБ.");return;}
  const formats:Record<string,string>={svg:"image/svg+xml",jpg:"image/jpeg",jpeg:"image/jpeg",png:"image/png",webp:"image/webp"};
  const mime=file.type||formats[file.name.split(".").pop()?.toLowerCase()??""];
  if(!["image/svg+xml","image/jpeg","image/png","image/webp"].includes(mime)){
   setPictureError("Поддерживаются PNG, JPG, WebP и SVG.");return;
  }
  const reader=new FileReader();
  reader.onload=()=>{
   if(typeof reader.result==="string")
    setPlate(prev=>({...prev,picture:{...prev.picture,image_data:reader.result as string,
     filename:file.name,filament_palette:[],color_overrides:[]}}));
  };
  reader.onerror=()=>setPictureError("Не удалось прочитать файл.");
  reader.readAsDataURL(file.type===mime?file:new Blob([file],{type:mime}));
 }
 async function save() {
  if(!isEditor) return;
  const id=projectId??crypto.randomUUID();
  const name=projectName.trim() || (kind==="plate"
   ?(plate.content_type==="image"?plate.picture.filename.replace(/\.[^.]+$/,""):
     plate.text.replace(/\s+/g," ").trim())
   :silhouette.filename.replace(/\.[^.]+$/,""));
  const entry:Project={id,name,kind,updatedAt:new Date().toISOString(),
   ...(kind==="plate"?{plate}:{silhouette})};
  try {await saveProject(entry);setProjectId(id);setProjectName(name);setToast("Проект сохранён в этом браузере.");}
  catch {setToast("Не удалось сохранить проект. Проверьте доступность IndexedDB.");}
 }
 function openProject(item:Project) {
  setSelectedContour(null);
  if(item.kind==="plate"&&item.plate){
   const legacy={...initialPicture,...(item.plate.picture??{})};
   if(legacy.algorithm==="floyd"){legacy.algorithm="median";legacy.dithering="floyd";}
   setPlate({...initialPlate,...item.plate,picture:legacy});
  }
  else if(item.silhouette)setSilhouette({...initialSilhouette,...item.silhouette,
   mount_type:item.silhouette.mount_type??(
    item.silhouette.attach_loop?(
     item.silhouette.loop_orientation==="upright"?"upright":"loop"):"none")});
  setProjectId(item.id);setProjectName(item.name);setView("iso");navigate(item.kind);
 }
 async function remove(id:string) {
  if(!window.confirm("Удалить сохранённый проект?"))return;
  try {await removeProject(id);await refreshGallery();}
  catch {setToast("Не удалось удалить проект.");}
 }
 async function download(format:"3mf"|"stl"|"stl-zip") {
  if(!isEditor||!model)return;
  setExporting(format);setError("");
  try {
   const response=await fetch("/api/export/"+format,{method:"POST",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(request())});
   if(!response.ok){const body=await response.json();throw new Error(body.detail||"Ошибка экспорта.");}
   const blob=await response.blob();
   const url=URL.createObjectURL(blob);
   const a=document.createElement("a");a.href=url;
   a.download=(projectName.trim()||"shapehatch").replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]/g,"_")+"."+ (format==="stl-zip"?"zip":format);
   document.body.appendChild(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),2000);
  } catch(ex) {setError(ex instanceof Error?ex.message:String(ex));}
  finally{setExporting(null);}
 }

 return <div className="app">
  <header className="header">
   <button type="button" className="brand" onClick={()=>navigate("home")} aria-label="На главную">
    <div className="brand-icon"><Shapes size={23} strokeWidth={2.2}/></div>
    <span>Shape<span className="brand-accent">Hatch</span></span>
    <span className="version">BETA 0.3.2</span>
   </button>
   <nav className="top-nav">
    <button onClick={()=>navigate("home")} className={section==="home"?"active":""}>Главная</button>
    <button onClick={()=>navigate("gallery")} className={section==="gallery"?"active":""}>
     <FolderOpen size={16}/> Моя галерея
    </button>
   </nav>
  </header>

  {section==="home"&&<main className="home">
   <div className="hero">
    <span className="eyebrow">ОНЛАЙН-МАСТЕРСКАЯ 3D-ПЕЧАТИ</span>
    <h1>Придумай форму.<br/><em>Создай вещь.</em></h1>
    <p>Готовые модели для 3D-принтера без сложных CAD-программ. Настройте размер, изучите модель со всех сторон и скачайте STL или 3MF.</p>
    <div className="hero-stat"><Check size={16}/> Без регистрации <span>·</span> Открытый код <span>·</span> Всё в браузере</div>
   </div>
   <h2 className="section-title">Что будем создавать?</h2>
   <div className="generator-grid">
    <button className="generator-card" onClick={()=>create("silhouette")}>
     <div className="card-art silhouette-art"><div className="goat-outline" dangerouslySetInnerHTML={{__html: goatDataUrl ? atob(goatDataUrl.split(",")[1]) : ""}}/></div>
     <div className="card-detail"><div className="card-icon"><FileImage size={23}/></div>
      <h3>Брелок из изображения</h3>
      <p>Загрузите силуэт или рисунок. Получите объёмную фигурку с отверстием для кольца.</p>
      <span className="card-action">Открыть генератор <Plus size={17}/></span></div>
    </button>
    <button className="generator-card" onClick={()=>create("plate")}>
     <div className="card-art plate-art"><div className="sample-plate">SHAPE<span>HATCH</span></div></div>
     <div className="card-detail"><div className="card-icon"><Type size={23}/></div>
      <h3>Табличка</h3>
      <p>Текст или многоцветная картинка, произвольная основа, крепление и магниты.</p>
      <span className="card-action">Открыть генератор <Plus size={17}/></span></div>
    </button>
    <div className="generator-card future-card">
     <div className="future-icon"><Box size={32}/></div><span className="soon">В РАЗРАБОТКЕ</span>
     <h3>Больше генераторов</h3><p>Вазы, коробки, корпуса, органайзеры и другие параметрические модели — в следующих версиях.</p>
    </div>
   </div>
   <footer className="footer">ShapeHatch · Сделано для творчества и 3D-печати · Open source</footer>
  </main>}

  {section==="gallery"&&<main className="gallery-page">
   <div className="page-heading"><div><span className="eyebrow">ЛОКАЛЬНЫЕ ПРОЕКТЫ</span><h1>Моя галерея</h1>
    <p>Проекты хранятся в этом браузере. Они не загружаются на сервер.</p></div>
    <button className="secondary-btn" onClick={()=>navigate("home")}><Plus size={18}/> Новый проект</button></div>
   <div className="gallery-filters">
    <button className={galleryFilter==="all"?"selected":""} onClick={()=>setGalleryFilter("all")}>Все проекты</button>
    <button className={galleryFilter==="silhouette"?"selected":""} onClick={()=>setGalleryFilter("silhouette")}>Силуэты</button>
    <button className={galleryFilter==="plate"?"selected":""} onClick={()=>setGalleryFilter("plate")}>Надписи</button>
   </div>
   {visibleProjects.length===0?<div className="empty-gallery"><FolderOpen size={45}/><h3>Пока нет сохранённых моделей</h3>
    <p>Создайте изделие и нажмите «Сохранить проект» в редакторе.</p>
    <button className="primary-btn" onClick={()=>navigate("home")}>Выбрать генератор</button></div>:
    <div className="saved-grid">{visibleProjects.map(item=><article className="saved-card" key={item.id}>
      <div className="saved-art">{item.kind==="plate"?<Type size={46}/>:<FileImage size={46}/>}</div>
      <div className="saved-info"><span className="eyebrow">{item.kind==="plate"?(item.plate?.content_type==="image"?"ТАБЛИЧКА С КАРТИНКОЙ":"ТАБЛИЧКА"):"СИЛУЭТ"}</span>
       <h3>{item.name}</h3><small>{new Date(item.updatedAt).toLocaleString("ru-RU")}</small>
       <div className="saved-actions"><button onClick={()=>openProject(item)}>Открыть и изменить</button>
       <button title="Удалить" aria-label="Удалить" onClick={()=>void remove(item.id)}><Trash2 size={16}/></button></div>
      </div></article>)}</div>}
  </main>}

  {isEditor&&<main className="workspace">
   <aside className="sidebar">
    <div className="sidebar-top"><button className="back-link" onClick={()=>navigate("home")}><ChevronLeft size={17}/> Генераторы</button>
     <h2>{kind==="silhouette"?"Фигура по контуру":"Табличка"}</h2>
     <p>{kind==="silhouette"?"Силуэт, внутренние контуры и крепление.":
      "Текст или многоцветная картинка, основа и крепление."}</p>
     <div className="wizard-steps" aria-label="Шаги редактирования">
      {wizardSteps.map((name,index)=><button type="button" key={index}
       className={editorStep===index?"active":""} aria-current={editorStep===index?"step":undefined}
       onClick={()=>goStep(index)}>
       <span>{index+1}</span>{name}
      </button>)}
     </div></div>

    <div className="settings-scroll">
    {kind==="plate"&&editorStep===0&&<section className="settings-group content-choice">
     <h3><Layers3 size={18}/> Что разместим на табличке?</h3>
     <div className="content-choice-grid">
      <button type="button" className={plate.content_type==="text"?"selected":""}
       onClick={()=>{changePlate("content_type","text");setOpenGroup("text");}}>
       <Type size={25}/><strong>Текст</strong><span>Надпись с рельефом или цветной вставкой</span>
      </button>
      <button type="button" className={plate.content_type==="image"?"selected":""}
       onClick={()=>{changePlate("content_type","image");setOpenGroup("picture");}}>
       <ImagePlus size={25}/><strong>Картинка</strong><span>Многоцветный рисунок на лицевой стороне</span>
      </button>
     </div>
    </section>}
    {editorStep===wizardSteps.length-1&&<section className="settings-group export-help">
     <h3><Download size={18}/> Готово к печати</h3>
     <p className="mount-instructions">3MF сохраняет отдельные объёмы каждого цвета и названия частей.
      Проверьте соответствие цветов выбранным катушкам в слайсере.</p>
     <p className="field-hint">Вернитесь к любому предыдущему шагу — настройки сохраняются,
      неизменённые узлы модели повторно используются из кэша.</p>
    </section>}
    {kind==="silhouette"?<>
     {editorStep===0&&<Accordion title="Изображение" icon={ImagePlus} opened={openGroup==="image"} onToggle={()=>toggleGroup("image")}>
      <label className="upload-box"><UploadCloud size={25}/><strong>Загрузить изображение</strong>
       <small>PNG, JPG, WebP, SVG · до 5 МБ</small>
       <input type="file" accept=".png,.jpg,.jpeg,.webp,.svg,image/png,image/jpeg,image/webp,image/svg+xml"
        onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f);e.target.value="";}}/>
      </label><p className="file-name">Файл: {silhouette.filename}</p>
      <OptionSelect label="Тип изображения" value={silhouette.mode}
       options={[{value:"filled",label:"Залитый силуэт"},{value:"cutouts",label:"Силуэт с отверстиями"},
        {value:"lines",label:"Контурный рисунок"}]}
       onChange={v=>changeSilhouette("mode",v as Silhouette["mode"])}/>
      <div className="field-row">
       <NumberInput label="Порог распознавания" value={silhouette.threshold} step={1} min={1} max={254}
         onChange={v=>changeSilhouette("threshold",v)}/>
       <NumberInput label="Сглаживание, мм" value={silhouette.smoothing_mm} step={0.05} min={0} max={2}
         onChange={v=>changeSilhouette("smoothing_mm",v)}/>
      </div><Toggle label="Инвертировать" checked={silhouette.invert} onChange={v=>changeSilhouette("invert",v)}/>
     </Accordion>}
     {editorStep===1&&<Accordion title={"Внутренние контуры"+(model?.inner_contours?.length?" · "+model.inner_contours.length:"")}
       icon={Layers3} opened={openGroup==="contours"} onToggle={()=>toggleGroup("contours")}>
      <p className="mount-instructions">Выберите контур в списке или нажмите на выделенную область прямо в 3D-просмотре.
       Вставка другого цвета формируется в верхних слоях детали.</p>
      {!model?.inner_contours?.length
       ?<p className="field-hint">Внутренние замкнутые контуры не обнаружены. Если это рисунок линиями,
         попробуйте режим «Контурный рисунок» и настройку порога распознавания.</p>
       :model.inner_contours.map((entry,index)=>{
        const style=silhouette.inner_contours?.find(x=>x.id===entry.id);
        const fill=style?.fill??(silhouette.mode==="cutouts"?"empty":"same");
        const active=selectedContour===entry.id;
        return <div key={entry.id} className={"contour-row"+(active?" active":"")}>
         <button type="button" className="contour-select" onClick={()=>setSelectedContour(entry.id)}>
          <span className="contour-marker">{index+1}</span> Внутренний контур {index+1}
          {active&&<Check size={15}/>}
         </button>
         <OptionSelect label="Режим заполнения" value={fill}
          options={[{value:"same",label:"Тот же материал"},{value:"other",label:"Другой материал / цвет"},
           {value:"empty",label:"Оставить пустым (сквозное отверстие)"}]}
          onChange={v=>changeInner(entry.id,{fill:v as InnerContourSetting["fill"]})}/>
         {fill==="other"&&<ColorInput label="Цвет вставки" value={style?.color??"#F26C50"}
          onChange={v=>changeInner(entry.id,{color:v})}/>}
        </div>;
       })}
      {model?.inner_contours.some(x=>
        (silhouette.inner_contours?.find(y=>y.id===x.id)?.fill??(silhouette.mode==="cutouts"?"empty":"same"))==="other")
        &&<NumberInput label="Глубина цветных вставок, мм" value={silhouette.inlay_depth_mm??0.8}
         min={0.2} max={Math.min(5,Math.max(0.2,silhouette.thickness_mm-0.3))}
         step={0.1} onChange={v=>changeSilhouette("inlay_depth_mm",v)}/>}
     </Accordion>}
     {editorStep===2&&<Accordion title="Размеры" icon={Settings2} opened={openGroup==="dimensions"} onToggle={()=>toggleGroup("dimensions")}>
      <div className="field-row"><NumberInput label="Ширина, мм" value={silhouette.width_mm} min={10} max={300}
       onChange={v=>changeSilhouette("width_mm",v)}/>
      {silhouetteMount==="upright"
       ?<label className="field"><span>Толщина брелка, мм (авто)</span>
         <input type="number" disabled readOnly value={Number((silhouette.loop_hole_mm+2*silhouette.loop_wall_mm).toFixed(2))}/></label>
       :<NumberInput label="Толщина, мм" value={silhouette.thickness_mm} min={0.6} max={25}
         onChange={v=>changeSilhouette("thickness_mm",v)}/>}</div>
      <ColorInput label="Цвет изделия" value={silhouette.color} onChange={v=>changeSilhouette("color",v)}/>
      <NumberInput label="Скругление верхней кромки, мм" value={silhouette.top_round_mm??0.3}
       min={0} max={0.4} step={0.05} onChange={v=>changeSilhouette("top_round_mm",v)}/>
      <small className="field-hint">0 — без скругления; рекомендуется 0,2–0,4 мм.</small>
     </Accordion>}
     {editorStep===3&&<section className="settings-group wizard-mount">
      <h3><Layers3 size={18}/> Крепление</h3>
      <AttachmentControls type={silhouetteMount}
       onTypeChange={v=>{
        changeSilhouette("mount_type",v);
        if(v==="magnets")setView("bottom");
       }}
       hole={silhouette.loop_hole_mm} wall={silhouette.loop_wall_mm}
       onHole={v=>changeSilhouette("loop_hole_mm",v)}
       onWall={v=>changeSilhouette("loop_wall_mm",v)}
       magnets={silhouette.magnets}
       onMagnets={v=>changeSilhouette("magnets",v)}/>
     </section>}
    </>:<>
     {(pictureMode?editorStep===1:editorStep===2)&&<Accordion title="Основа" icon={Box} opened={openGroup==="base"} onToggle={()=>toggleGroup("base")}>
      <OptionSelect label="Форма" value={plate.shape} onChange={v=>changePlate("shape",v as Plate["shape"])}
       options={[{value:"rounded",label:"Скруглённый прямоугольник"},{value:"rectangle",label:"Прямоугольник"},
        {value:"oval",label:"Овал"},{value:"circle",label:"Круг"},{value:"hexagon",label:"Шестиугольник"}]}/>
      <div className="field-row">
       <NumberInput label="Ширина, мм" value={plate.width_mm} min={20} max={300} onChange={v=>changePlate("width_mm",v)}/>
       <NumberInput label="Высота, мм" value={plate.height_mm} min={12} max={200} onChange={v=>changePlate("height_mm",v)}/>
      </div>
      <div className="field-row">
       {currentMount==="upright"
        ?<label className="field"><span>Толщина основы, мм (авто)</span>
          <input type="number" disabled readOnly value={Number((plate.mount_hole_mm+2*plate.mount_wall_mm).toFixed(2))}/></label>
        :<NumberInput label="Толщина, мм" value={plate.thickness_mm} min={0.8} max={25}
          onChange={v=>changePlate("thickness_mm",v)}/>}
       {plate.shape==="rounded"&&<NumberInput label="Радиус углов, мм" value={plate.corner_radius_mm} min={0} max={50}
        onChange={v=>changePlate("corner_radius_mm",v)}/>}
      </div>
      {plate.content_type==="text"&&<div className="field-row">
       <NumberInput label="Сдвиг текста X, мм" value={plate.text_x_mm} min={-150} max={150}
        onChange={v=>changePlate("text_x_mm",v)}/>
       <NumberInput label="Сдвиг текста Y, мм" value={plate.text_y_mm} min={-100} max={100}
        onChange={v=>changePlate("text_y_mm",v)}/>
      </div>}
      <ColorInput label="Цвет основы" value={plate.base_color} onChange={v=>changePlate("base_color",v)}/>
      <NumberInput label="Скругление верхней кромки, мм" value={plate.top_round_mm??0.3}
       min={0} max={0.4} step={0.05} onChange={v=>changePlate("top_round_mm",v)}/>
      <small className="field-hint">0 — без скругления; рекомендуется 0,2–0,4 мм.</small>
     </Accordion>}
     {editorStep===mountStep&&<section className="settings-group wizard-mount">
      <h3><Layers3 size={18}/> Крепление</h3>
      <AttachmentControls type={plate.mount_type}
       onTypeChange={v=>{
        changePlate("mount_type",v);
        if(v==="magnets")setView(plate.content_type==="image"?"top":"bottom");
       }}
       hole={plate.mount_hole_mm} wall={plate.mount_wall_mm}
       onHole={v=>changePlate("mount_hole_mm",v)}
       onWall={v=>changePlate("mount_wall_mm",v)}
       magnets={plate.magnets}
       onMagnets={v=>changePlate("magnets",v)}/>
     </section>}
     {pictureMode&&editorStep===2&&<section className="settings-group picture-editor">
      <h3><ImagePlus size={18}/> Картинка и масштаб</h3>
      <p className="field-hint">Размер таблички: {plate.width_mm} × {plate.height_mm} мм.
       Для изменения основы вернитесь к шагу 2.</p>
      <label className="upload-box"><UploadCloud size={25}/><strong>Загрузить картинку</strong>
       <small>PNG, JPG, WebP, SVG · до 5 МБ</small>
       <input type="file" accept=".png,.jpg,.jpeg,.webp,.svg,image/png,image/jpeg,image/webp,image/svg+xml"
        onChange={e=>{const file=e.target.files?.[0];if(file)void uploadPicture(file);e.target.value="";}}/>
      </label>
      {plate.picture.filename&&<p className="file-name">Файл: {plate.picture.filename}</p>}
      {plate.picture.image_data&&<div className="picture-comparison single-picture">
       <div><strong>Исходное изображение</strong>
        <img src={plate.picture.image_data} alt="Исходное изображение"/></div>
      </div>}
      <OptionSelect label="Подгонка к табличке" value={plate.picture.fit_mode??"fit"}
       options={[{value:"fit",label:"Вписать целиком"},{value:"fill",label:"Заполнить табличку (с обрезкой)"},
        {value:"width",label:"По ширине"},{value:"height",label:"По высоте"},
        {value:"manual",label:"Задать ширину вручную"}]}
       onChange={v=>changePicture("fit_mode",v as PictureSettings["fit_mode"])}/>
      {plate.picture.fit_mode==="manual"&&<NumberInput label="Ширина картинки, мм"
       value={plate.picture.width_mm} min={5} max={280} step={0.5}
       onChange={v=>changePicture("width_mm",v)}/>}
      <NumberInput label="Масштаб, %" value={Math.round((plate.picture.scale??1)*100)}
       min={10} max={500} step={5} onChange={v=>changePicture("scale",v/100)}/>
      {["fit","fill"].includes(plate.picture.fit_mode??"fit")&&
       <Toggle label="Сохранять пропорции" checked={plate.picture.preserve_aspect??true}
        onChange={v=>changePicture("preserve_aspect",v)}/>}
      <div className="field-row">
       <NumberInput label="Сдвиг X, мм" value={plate.picture.x_mm}
        min={-150} max={150} onChange={v=>changePicture("x_mm",v)}/>
       <NumberInput label="Сдвиг Y, мм" value={plate.picture.y_mm}
        min={-100} max={100} onChange={v=>changePicture("y_mm",v)}/>
      </div>
      <NumberInput label="Толщина цветного слоя, мм" value={plate.picture.layer_mm}
       min={0.2} max={2} step={0.1} onChange={v=>changePicture("layer_mm",v)}/>
      <small className="field-hint">Картинка помещается на нижнюю лицевую поверхность
       (Z=0). Выступающие за основу края обрезаются автоматически.</small>
     </section>}
     {pictureMode&&editorStep===3&&<section className="settings-group picture-editor">
      <h3><ImagePlus size={18}/> Цвета и оптимизация</h3>
      {!plate.picture.image_data?<p className="field-hint">Сначала загрузите рисунок на шаге 3.</p>:<>
      <div className="field-row">
       <OptionSelect label="Тип изображения" value={plate.picture.image_kind??"logo"}
        options={[{value:"logo",label:"Логотип / пиктограмма (резкие края)"},
         {value:"photo",label:"Фотография / градиенты"}]}
        onChange={v=>changePicture("image_kind",v as PictureSettings["image_kind"])}/>
       <NumberInput label="Количество цветов" value={plate.picture.color_count}
        min={2} max={16} step={1} onChange={v=>changePicture("color_count",v)}/>
      </div>
      <OptionSelect label="Алгоритм подбора цветов" value={plate.picture.algorithm}
       options={[{value:"auto",label:"Авто (для логотипов сохранять исходные цвета)"},
        {value:"original",label:"Без оптимизации (исходные цвета)"},
        {value:"nearest",label:"Ближайшие преобладающие цвета"},
        {value:"median",label:"Median Cut"},{value:"kmeans",label:"K-Means"}]}
       onChange={v=>changePicture("algorithm",v as PictureSettings["algorithm"])}/>
      <OptionSelect label="Дизеринг" value={plate.picture.dithering??"none"}
       options={[{value:"none",label:"Без дизеринга — чёткие границы"},
        {value:"floyd",label:"Floyd–Steinberg"},{value:"atkinson",label:"Atkinson"},
        {value:"bayer",label:"Bayer 4×4"}]}
       onChange={v=>changePicture("dithering",v as PictureSettings["dithering"])}/>
      <NumberInput label="Детализация 3D-рисунка (пикселей по длинной стороне)"
       value={plate.picture.resolution} min={16} max={320} step={16}
       onChange={v=>changePicture("resolution",v)}/>
      <small className="field-hint">Выше детализация — больше мелких объёмов и тяжелее 3MF.
       Для печати логотипов обычно подходит 128–192.</small>
      {pictureError&&<p className="field-hint" role="alert">{pictureError}</p>}
      {pictureBusy&&<p className="field-hint">Оптимизация изображения…</p>}
      <div className="picture-comparison">
       <div><strong>Оригинал</strong><img src={plate.picture.image_data} alt="Исходное изображение"/></div>
       <div><strong>После оптимизации</strong>{picturePreview&&
        <img src={picturePreview.image_url} alt="Результат выбранного алгоритма"/>}</div>
      </div>
      {picturePreview&&<>
       <label className="toggle"><span>Использовать цвета своих катушек</span>
        <input type="checkbox" checked={plate.picture.filament_palette.length>0}
         onChange={e=>changePicture("filament_palette",
          e.target.checked?picturePreview.colors.slice(0,plate.picture.color_count):[])}/></label>
       {plate.picture.filament_palette.map((color,index)=><ColorInput key={index}
        label={"Катушка "+(index+1)} value={color}
        onChange={v=>changePicture("filament_palette",
         plate.picture.filament_palette.map((c,i)=>i===index?v:c))}/>)}
       <p className="field-hint">Можно заменить любой цвет отдельно, не меняя цветовые области.</p>
       {picturePreview.colors.map((color,index)=><div key={index} className="palette-override">
        <ColorInput label={"Цвет "+(index+1)+" · "+picturePreview.pixel_counts[index]+" пикс."}
         value={plate.picture.color_overrides[index]??color}
         onChange={v=>changePicture("color_overrides",
          picturePreview.colors.map((c,i)=>i===index?v:(plate.picture.color_overrides[i]??c)))}/>
       </div>)}
       {plate.picture.color_overrides.length>0&&
        <button type="button" className="secondary-btn"
         onClick={()=>changePicture("color_overrides",[])}>Сбросить ручные цвета</button>}
      </>}
      </>}
     </section>}
     {editorStep===1&&plate.content_type==="text"&&<Accordion title="Надпись" icon={Type} opened={openGroup==="text"} onToggle={()=>toggleGroup("text")}>
      <label className="field"><span>Текст</span><textarea rows={4} maxLength={120} value={plate.text}
       onChange={e=>changePlate("text",e.target.value.replace(/\r\n?/g,"\n"))}/>
       <small className="field-hint">Enter — новая строка. Все строки видны в 3D-просмотре.</small></label>
      <OptionSelect label="Шрифт" value={plate.font} onChange={v=>changePlate("font",v as Plate["font"])}
       options={[{value:"sans",label:"DejaVu Sans"},{value:"bold",label:"DejaVu Sans Bold"},
        {value:"serif",label:"DejaVu Serif"},{value:"mono",label:"DejaVu Mono"},
        {value:"russo",label:"Russo One — массивный"},{value:"play",label:"Play Bold — техно"},
        {value:"pt-sans",label:"PT Sans — универсальный"},{value:"lobster",label:"Lobster — рукописный"},
        {value:"rubik-mono",label:"Rubik Mono One — геометрический"},
        {value:"unbounded",label:"Unbounded — современный"},
        {value:"comfortaa",label:"Comfortaa — округлый"},
        {value:"terminus",label:"Terminus TTF — пиксельный"}]}/>
      <div className="field-row">
       <OptionSelect label="Выравнивание" value={plate.text_align??"center"}
        options={[{value:"left",label:"По левому краю"},{value:"center",label:"По центру"},{value:"right",label:"По правому краю"}]}
        onChange={v=>changePlate("text_align",v as Plate["text_align"])}/>
       <NumberInput label="Интервал строк, мм" value={plate.line_spacing_mm??1.5}
        min={0} max={15} step={0.5} onChange={v=>changePlate("line_spacing_mm",v)}/>
      </div>
      <OptionSelect label="Тип надписи" value={plate.text_style} onChange={v=>changePlate("text_style",v as Plate["text_style"])}
       options={[{value:"raised",label:"Выпуклая"},{value:"inlay",label:"Цветная вставка"},{value:"engraved",label:"Гравировка"}]}/>
      <div className="field-row">
       <NumberInput label="Размер шрифта, мм" value={plate.font_size_mm} min={2} max={60}
        onChange={v=>changePlate("font_size_mm",v)}/>
       <NumberInput label="Рельеф, мм" value={plate.text_depth_mm} min={0.2} max={5}
        onChange={v=>changePlate("text_depth_mm",v)}/>
      </div>
      {plate.text_style!=="engraved"&&<ColorInput label="Цвет надписи" value={plate.text_color}
       onChange={v=>changePlate("text_color",v)}/>}
     </Accordion>}
    </>}
    </div>
    <div className="wizard-navigation">
     <button type="button" disabled={editorStep===0} onClick={()=>goStep(editorStep-1)}>
      <ChevronLeft size={16}/> Назад
     </button>
     <span>Шаг {editorStep+1} из {wizardSteps.length}</span>
     <button type="button" disabled={editorStep===wizardSteps.length-1}
      onClick={()=>goStep(editorStep+1)}>
      Далее <ChevronDown size={15} className="next-arrow"/>
     </button>
    </div>
    <div className="sidebar-footer">
     <label className="project-label">Название проекта
      <input type="text" placeholder={kind==="silhouette"?"Козёл — брелок":(
       plate.content_type==="image"?plate.picture.filename:plate.text.replace(/\s+/g," ").trim())}
       value={projectName} onChange={e=>setProjectName(e.target.value)} maxLength={120}/>
     </label>
     <button className="save-btn" onClick={()=>void save()}><Save size={17}/> Сохранить проект</button>
     <small>Сохраняется локально в вашем браузере</small>
    </div>
   </aside>

   <section className="editor-main">
    <div className="editor-bar"><div className="editor-title"><strong>3D-просмотр</strong><span>Масштабируйте, вращайте, перемещайте содержимое и крепления</span></div>
     <div className="view-buttons">{views.map(v=><button key={v.id} className={view===v.id?"selected":""}
      onClick={()=>setView(v.id)}>{v.label}</button>)}</div></div>
    <div className="scene">
     <Viewer key={kind} preview={model} view={view}
       mountEnabled={editorStep===mountStep&&["hole","loop","upright"].includes(currentMount)}
       mountPosition={kind==="plate"?plate.mount_contour_t??null:silhouette.loop_contour_t??null}
       onMountPositionChange={fraction=>kind==="plate"
        ?changePlate("mount_contour_t",fraction)
        :changeSilhouette("loop_contour_t",fraction)}
       selectedContour={kind==="silhouette"?selectedContour:null}
       onContourSelect={selectContour}
       magnetEnabled={editorStep===mountStep&&currentMount==="magnets"}
       magnetPositions={(kind==="silhouette"?silhouette.magnets:plate.magnets).positions.map(p=>[p.x_mm,p.y_mm])}
       onMagnetPositionChange={updateMagnet}
       textPosition={kind==="plate"&&editorStep===2?(
        plate.content_type==="image"?[plate.picture.x_mm,plate.picture.y_mm]:
        [plate.text_x_mm,plate.text_y_mm]):null}
       onTextPositionChange={(x,y)=>{
        if(plate.content_type==="image")
         setPlate(prev=>({...prev,picture:{...prev.picture,x_mm:x,y_mm:y}}));
        else setPlate(prev=>({...prev,text_x_mm:x,text_y_mm:y}));
       }}/>
     <div className="scene-info"><span><ZoomIn size={14}/> Колесо — масштаб</span>
      <span><RotateCcw size={14}/> ЛКМ — вращение</span><span>ПКМ — панорама</span>
      {kind==="plate"&&editorStep===2&&<span>Оранжевая ручка — {plate.content_type==="image"?"картинка":"текст"}</span>}
      {editorStep===mountStep&&currentMount==="magnets"&&<span>Сиреневые ручки — магниты</span>}
      {kind==="silhouette"&&!!model?.inner_contours?.length&&<span>Нажмите на внутренний контур — его настройки</span>}</div>
     {busy&&<div className="scene-spinner"><LoaderCircle size={20} className="spin"/> Построение модели…</div>}
     {error&&<div className="scene-error"><CircleHelp size={18}/>
       <span>{error}{model&&<small className="stale-model-note">
        На экране предыдущая корректная модель. Текущие изменения ещё не построены.
       </small>}</span></div>}
    </div>
    <div className="export-panel"><div className="model-info">
     <span className={"status "+(model&&!error&&!busy?"ready":"pending")}>
      {model&&!error&&!busy?<Check size={15}/>:<LoaderCircle size={15}/>}
      {error?"Ошибка построения":busy?"Перестроение…":model?"Модель готова":"Обработка"}</span>
     {model&&<span className="model-dims">Габариты: {model.size_mm.join(" × ")} мм</span>}
     {model?.warnings.map((warning,i)=><span className="model-warning" key={i}>{warning}</span>)}
    </div>
    <div className="exports">
     <button className="export-main" disabled={!model||busy||!!error||!!exporting} onClick={()=>void download("3mf")}>
      {exporting==="3mf"?<LoaderCircle size={17} className="spin"/>:<Download size={17}/>} Скачать 3MF</button>
     <button className="export-alt" disabled={!model||busy||!!error||!!exporting} onClick={()=>void download("stl")}>STL</button>
     <button className="export-alt" disabled={!model||busy||!!error||!!exporting} onClick={()=>void download("stl-zip")}>STL ZIP</button>
    </div></div>
   </section>
  </main>}
  {toast&&<div className="toast"><span>{toast}</span><button aria-label="Закрыть" onClick={()=>setToast("")}><X size={16}/></button></div>}
 </div>;
}
