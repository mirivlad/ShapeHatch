import type { Plate, Silhouette, MagnetSettings, PictureSettings } from "./types";
export const goatSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 135" width="180" height="135">'+
'<path fill="#131313" d="M 15 64 L 23 60 L 29 67 L 38 57 L 62 52 L 78 50 L 91 49 L 107 40 L 116 32 L 115 19 L 120 12 L 124 27 L 130 18 L 132 33 L 145 40 L 152 47 L 148 54 L 136 55 L 131 51 L 120 54 L 112 65 L 112 88 L 108 113 L 98 113 L 100 91 L 93 75 L 76 80 L 64 95 L 60 114 L 49 114 L 51 96 L 55 77 L 39 77 L 33 92 L 26 92 L 29 77 L 19 73 Z"/>'+
'<path fill="#131313" d="M 133 50 L 127 66 L 123 67 L 126 54 Z"/></svg>';
export const goatDataUrl="data:image/svg+xml;base64,"+btoa(goatSvg);
export const initialMagnets:MagnetSettings={
 shape:"round",diameter_mm:6,width_mm:10,height_mm:5,depth_mm:2,
 clearance_mm:0.2,positions:[{x_mm:0,y_mm:0}]
};
export const initialPicture:PictureSettings={
 image_data:"",filename:"",algorithm:"auto",dithering:"none",image_kind:"logo",
 fit_mode:"fit",scale:1,preserve_aspect:true,color_count:4,resolution:160,
 filament_palette:[],color_overrides:[],width_mm:45,x_mm:0,y_mm:0,layer_mm:0.4
};
export const initialSilhouette: Silhouette = {
 image_data:goatDataUrl,filename:"goat.svg",width_mm:55,thickness_mm:3,
 threshold:140,invert:false,mode:"filled",smoothing_mm:0.12,
 top_round_mm:0.3,inlay_depth_mm:0.8,inner_contours:[],
 attach_loop:true,mount_type:"loop",magnets:structuredClone(initialMagnets),loop_side:"top",loop_position:0.62,
 loop_orientation:"flat",loop_contour_t:null,
 loop_hole_mm:5,loop_wall_mm:2.2,color:"#293840"};
export const initialPlate: Plate = {
 text:"МОЙ БРЕЛОК",width_mm:90,height_mm:32,thickness_mm:3,
 shape:"rounded",corner_radius_mm:5,top_round_mm:0.3,
 content_type:"text",picture:structuredClone(initialPicture),
 magnets:structuredClone(initialMagnets),mount_type:"none",mount_contour_t:null,
 mount_side:"top",mount_position:0.5,mount_hole_mm:5,mount_wall_mm:2.3,
 font:"sans",font_size_mm:8,
 text_align:"center",line_spacing_mm:1.5,
 text_x_mm:0,text_y_mm:0,text_depth_mm:0.8,text_style:"raised",
 base_color:"#246C82",text_color:"#F7F8F4"};
