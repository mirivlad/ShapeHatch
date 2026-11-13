import { useCallback, useEffect, useState } from "react";
import {
  Box, Check, ChevronLeft, CircleHelp, Download, FileImage, FolderOpen, ImagePlus,
  Layers3, LoaderCircle, Plus, RotateCcw, Save, Settings2, Shapes, Trash2,
  Type, UploadCloud, X, ZoomIn
} from "lucide-react";
import { Viewer, type CameraView } from "./Viewer";
import { goatDataUrl, initialPlate, initialSilhouette } from "./sample";
import { getProjects, removeProject, saveProject } from "./storage";
import type { Plate, Preview, Project, Section, Silhouette } from "./types";

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

const views:{id:CameraView;label:string}[]=[
 {id:"iso",label:"3D"},{id:"top",label:"Сверху"},{id:"front",label:"Спереди"},
 {id:"left",label:"Слева"},{id:"right",label:"Справа"},{id:"bottom",label:"Снизу"}];

export function App() {
 const [section,setSection]=useState<Section>("home");
 const [silhouette,setSilhouette]=useState<Silhouette>(initialSilhouette);
 const [plate,setPlate]=useState<Plate>(initialPlate);
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
 const changeSilhouette=<K extends keyof Silhouette>(key:K,value:Silhouette[K])=>setSilhouette(prev=>({...prev,[key]:value}));
 const changePlate=<K extends keyof Plate>(key:K,value:Plate[K])=>setPlate(prev=>({...prev,[key]:value}));
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
    if(!abort.signal.aborted) {setModel(null);setError(ex instanceof Error?ex.message:String(ex));}
   } finally {if(!abort.signal.aborted)setBusy(false);}
  },480);
  return ()=>{clearTimeout(timeout);abort.abort();};
 },[isEditor,request]);

 async function refreshGallery() {
  try {setProjects(await getProjects());}
  catch {setToast("Не удалось открыть локальную галерею.");}
 }
 function navigate(next:Section) {
  setSection(next);setModel(null);setError("");
  if(next==="gallery")void refreshGallery();
 }
 function create(next:"silhouette"|"plate") {
  setProjectId(null);
  setProjectName("");
  setSilhouette(initialSilhouette);
  setPlate(initialPlate);
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
   changeSilhouette("image_data",reader.result);changeSilhouette("filename",file.name);}};
  reader.onerror=()=>setError("Не удалось прочитать файл.");
  reader.readAsDataURL(file.type === format ? file : new Blob([file], {type: format}));
 }
 async function save() {
  if(!isEditor) return;
  const id=projectId??crypto.randomUUID();
  const name=projectName.trim() || (kind==="plate" ? plate.text.replace(/\s+/g," ").trim() : silhouette.filename.replace(/\.[^.]+$/,""));
  const entry:Project={id,name,kind,updatedAt:new Date().toISOString(),
   ...(kind==="plate"?{plate}:{silhouette})};
  try {await saveProject(entry);setProjectId(id);setProjectName(name);setToast("Проект сохранён в этом браузере.");}
  catch {setToast("Не удалось сохранить проект. Проверьте доступность IndexedDB.");}
 }
 function openProject(item:Project) {
  if(item.kind==="plate"&&item.plate)setPlate({...initialPlate,...item.plate});
  else if(item.silhouette)setSilhouette({...initialSilhouette,...item.silhouette});
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
    <span className="version">BETA 0.1</span>
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
      <h3>Табличка с надписью</h3>
      <p>Создайте именной шильдик или табличку с выпуклым текстом и двумя цветами.</p>
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
      <div className="saved-info"><span className="eyebrow">{item.kind==="plate"?"ТАБЛИЧКА":"СИЛУЭТ"}</span>
       <h3>{item.name}</h3><small>{new Date(item.updatedAt).toLocaleString("ru-RU")}</small>
       <div className="saved-actions"><button onClick={()=>openProject(item)}>Открыть и изменить</button>
       <button title="Удалить" aria-label="Удалить" onClick={()=>void remove(item.id)}><Trash2 size={16}/></button></div>
      </div></article>)}</div>}
  </main>}

  {isEditor&&<main className="workspace">
   <aside className="sidebar">
    <div className="sidebar-top"><button className="back-link" onClick={()=>navigate("home")}><ChevronLeft size={17}/> Генераторы</button>
     <h2>{kind==="silhouette"?"Брелок из изображения":"Табличка с текстом"}</h2>
     <p>{kind==="silhouette"?"Настройте форму и положение петельки.":"Настройте основу, текст и цветовые слои."}</p></div>

    <div className="settings-scroll">
    {kind==="silhouette"?<>
     <div className="settings-group"><h3><ImagePlus size={18}/> Изображение</h3>
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
     </div>
     <div className="settings-group"><h3><Settings2 size={18}/> Размеры</h3>
      <div className="field-row"><NumberInput label="Ширина, мм" value={silhouette.width_mm} min={10} max={300}
       onChange={v=>changeSilhouette("width_mm",v)}/>
      <NumberInput label="Толщина, мм" value={silhouette.thickness_mm} min={0.6} max={25}
       onChange={v=>changeSilhouette("thickness_mm",v)}/></div>
      <ColorInput label="Цвет изделия" value={silhouette.color} onChange={v=>changeSilhouette("color",v)}/>
     </div>
     <div className="settings-group"><h3><Layers3 size={18}/> Петелька для кольца</h3>
      <Toggle label="Добавить петельку" checked={silhouette.attach_loop} onChange={v=>changeSilhouette("attach_loop",v)}/>
      {silhouette.attach_loop&&<>
       <OptionSelect label="Ориентация петельки" value={silhouette.loop_orientation??"flat"}
        options={[{value:"flat",label:"В плоскости брелка"},
         {value:"upright",label:"Перпендикулярная"}]}
        onChange={v=>changeSilhouette("loop_orientation",v as Silhouette["loop_orientation"])}/>
       <p className="mount-instructions">Перетащите бирюзовый маркер на 3D-модели — он прилипает к внешнему контуру.</p>
       <label className="field"><span>Точное положение по контуру: {Math.round(100*(silhouette.loop_contour_t??model?.mount_fraction??0))}%</span>
        <input type="range" min={0} max={1} step={0.001}
         value={silhouette.loop_contour_t??model?.mount_fraction??0}
         onChange={e=>changeSilhouette("loop_contour_t",Number(e.target.value))}/></label>
       <div className="field-row">
        <NumberInput label="Диаметр отверстия, мм" value={silhouette.loop_hole_mm} min={2} max={12}
         onChange={v=>changeSilhouette("loop_hole_mm",v)}/>
        <NumberInput label="Стенка, мм" value={silhouette.loop_wall_mm} min={1} max={6}
         onChange={v=>changeSilhouette("loop_wall_mm",v)}/>
       </div>
      </>}
     </div>
    </>:<>
     <div className="settings-group"><h3><Box size={18}/> Основа</h3>
      <OptionSelect label="Форма" value={plate.shape} onChange={v=>changePlate("shape",v as Plate["shape"])}
       options={[{value:"rounded",label:"Скруглённый прямоугольник"},{value:"rectangle",label:"Прямоугольник"},
        {value:"oval",label:"Овал"},{value:"circle",label:"Круг"},{value:"hexagon",label:"Шестиугольник"}]}/>
      <div className="field-row">
       <NumberInput label="Ширина, мм" value={plate.width_mm} min={20} max={300} onChange={v=>changePlate("width_mm",v)}/>
       <NumberInput label="Высота, мм" value={plate.height_mm} min={12} max={200} onChange={v=>changePlate("height_mm",v)}/>
      </div>
      <div className="field-row">
       <NumberInput label="Толщина, мм" value={plate.thickness_mm} min={0.8} max={25} onChange={v=>changePlate("thickness_mm",v)}/>
       {plate.shape==="rounded"&&<NumberInput label="Радиус углов, мм" value={plate.corner_radius_mm} min={0} max={50}
        onChange={v=>changePlate("corner_radius_mm",v)}/>}
      </div>
      <ColorInput label="Цвет основы" value={plate.base_color} onChange={v=>changePlate("base_color",v)}/>
     </div>
     <div className="settings-group"><h3><Layers3 size={18}/> Крепление для кольца</h3>
      <OptionSelect label="Тип крепления" value={plate.mount_type??"none"}
       options={[{value:"none",label:"Без крепления"},{value:"hole",label:"Отверстие в плашке"},
        {value:"loop",label:"Петелька в плоскости"},{value:"upright",label:"Петелька перпендикулярно"}]}
       onChange={v=>changePlate("mount_type",v as Plate["mount_type"])}/>
      {plate.mount_type!=="none"&&<>
       <p className="mount-instructions">Перетащите бирюзовый маркер прямо по контуру модели.</p>
       <label className="field"><span>Точное положение по контуру: {Math.round(100*(plate.mount_contour_t??model?.mount_fraction??0))}%</span>
        <input type="range" min={0} max={1} step={0.001}
         value={plate.mount_contour_t??model?.mount_fraction??0}
         onChange={e=>changePlate("mount_contour_t",Number(e.target.value))}/></label>
       <div className="field-row">
        <NumberInput label="Диаметр отверстия, мм" value={plate.mount_hole_mm}
         min={2} max={12} onChange={v=>changePlate("mount_hole_mm",v)}/>
        <NumberInput label="Толщина стенки, мм" value={plate.mount_wall_mm}
         min={1} max={6} onChange={v=>changePlate("mount_wall_mm",v)}/>
       </div><small className="field-hint">Два положения ушка: в плоскости или перпендикулярно ей. Отверстие внутри плашки — сквозное.</small>
      </>}
     </div>
     <div className="settings-group"><h3><Type size={18}/> Надпись</h3>
      <label className="field"><span>Текст</span><textarea rows={4} maxLength={120} value={plate.text}
       onChange={e=>changePlate("text",e.target.value.replace(/\r\n?/g,"\n"))}/>
       <small className="field-hint">Enter — новая строка. Все строки видны в 3D-просмотре.</small></label>
      <OptionSelect label="Шрифт" value={plate.font} onChange={v=>changePlate("font",v as Plate["font"])}
       options={[{value:"sans",label:"DejaVu Sans"},{value:"bold",label:"DejaVu Sans Bold"},
        {value:"serif",label:"DejaVu Serif"},{value:"mono",label:"DejaVu Mono"}]}/>
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
      <div className="field-row">
       <NumberInput label="Сдвиг X, мм" value={plate.text_x_mm} min={-150} max={150}
        onChange={v=>changePlate("text_x_mm",v)}/>
       <NumberInput label="Сдвиг Y, мм" value={plate.text_y_mm} min={-100} max={100}
        onChange={v=>changePlate("text_y_mm",v)}/>
      </div>
      {plate.text_style!=="engraved"&&<ColorInput label="Цвет надписи" value={plate.text_color}
       onChange={v=>changePlate("text_color",v)}/>}
     </div>
    </>}
    </div>
    <div className="sidebar-footer">
     <label className="project-label">Название проекта
      <input type="text" placeholder={kind==="silhouette"?"Козёл — брелок":plate.text.replace(/\s+/g," ").trim()}
       value={projectName} onChange={e=>setProjectName(e.target.value)} maxLength={120}/>
     </label>
     <button className="save-btn" onClick={()=>void save()}><Save size={17}/> Сохранить проект</button>
     <small>Сохраняется локально в вашем браузере</small>
    </div>
   </aside>

   <section className="editor-main">
    <div className="editor-bar"><div className="editor-title"><strong>3D-просмотр</strong><span>Масштабируйте, вращайте и перетаскивайте крепление</span></div>
     <div className="view-buttons">{views.map(v=><button key={v.id} className={view===v.id?"selected":""}
      onClick={()=>setView(v.id)}>{v.label}</button>)}</div></div>
    <div className="scene">
     <Viewer key={kind} preview={model} view={view}
       mountEnabled={kind==="plate"?plate.mount_type!=="none":silhouette.attach_loop}
       mountPosition={kind==="plate"?plate.mount_contour_t??null:silhouette.loop_contour_t??null}
       onMountPositionChange={fraction=>kind==="plate"
        ?changePlate("mount_contour_t",fraction)
        :changeSilhouette("loop_contour_t",fraction)}/>
     <div className="scene-info"><span><ZoomIn size={14}/> Колесо — масштаб</span>
      <span><RotateCcw size={14}/> ЛКМ — вращение</span><span>ПКМ — панорама</span></div>
     {busy&&<div className="scene-spinner"><LoaderCircle size={20} className="spin"/> Построение модели…</div>}
     {error&&<div className="scene-error"><CircleHelp size={18}/>{error}</div>}
    </div>
    <div className="export-panel"><div className="model-info">
     <span className={"status "+(model?"ready":"pending")}>{model?<Check size={15}/>:<LoaderCircle size={15}/>}
      {model?"Модель готова":error?"Нужны исправления":"Обработка"}</span>
     {model&&<span className="model-dims">Габариты: {model.size_mm.join(" × ")} мм</span>}
     {model?.warnings.map((warning,i)=><span className="model-warning" key={i}>{warning}</span>)}
    </div>
    <div className="exports">
     <button className="export-main" disabled={!model||busy||!!exporting} onClick={()=>void download("3mf")}>
      {exporting==="3mf"?<LoaderCircle size={17} className="spin"/>:<Download size={17}/>} Скачать 3MF</button>
     <button className="export-alt" disabled={!model||busy||!!exporting} onClick={()=>void download("stl")}>STL</button>
     <button className="export-alt" disabled={!model||busy||!!exporting} onClick={()=>void download("stl-zip")}>STL ZIP</button>
    </div></div>
   </section>
  </main>}
  {toast&&<div className="toast"><span>{toast}</span><button aria-label="Закрыть" onClick={()=>setToast("")}><X size={16}/></button></div>}
 </div>;
}
