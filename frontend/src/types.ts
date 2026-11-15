export type Section = "home" | "silhouette" | "plate" | "box" | "gallery";
export type Vec3 = [number,number,number];
export type Part = { name:string; color:string; vertices:Vec3[]; faces:Vec3[] };
export type InnerContourSetting = {id:string; fill:"same"|"other"|"empty"; color:string};
export type InnerContourPreview = {id:string; points:[number,number][]; fill:"same"|"other"|"empty"};
export type MagnetPoint={x_mm:number;y_mm:number};
export type MagnetSettings={
 shape:"round"|"rectangle"; diameter_mm:number; width_mm:number;height_mm:number;
 depth_mm:number;clearance_mm:number;positions:MagnetPoint[];
};
export type PictureSettings={
 image_data:string;filename:string;algorithm:"auto"|"original"|"nearest"|"median"|"kmeans"|"floyd";
 dithering:"none"|"floyd"|"atkinson"|"bayer";image_kind:"logo"|"photo";
 fit_mode:"fit"|"fill"|"width"|"height"|"manual";scale:number;preserve_aspect:boolean;
 color_count:number;resolution:number;filament_palette:string[];color_overrides:string[];
 width_mm:number;x_mm:number;y_mm:number;layer_mm:number;
};
export type PicturePreview={image_url:string;colors:string[];pixel_width:number;pixel_height:number;pixel_counts:number[]};
export type MountType="none"|"hole"|"loop"|"upright"|"magnets";
export type Preview = { parts:Part[]; size_mm:number[]; warnings:string[];
 mount_contour:number[][]; mount_fraction:number|null; mount_surface_z:number;
 text_bounds_mm:number[]|null; text_surface_z:number;
 magnet_positions:number[][];magnet_surface_z:number;
 image_preview_url:string|null;image_palette:string[]; inner_contours:InnerContourPreview[] };
export type Silhouette = {
 image_data:string; filename:string; width_mm:number; thickness_mm:number;
 threshold:number; invert:boolean; mode:"filled"|"cutouts"|"lines";
 smoothing_mm:number; mount_type?:MountType|null; magnets:MagnetSettings; top_round_mm:number; inlay_depth_mm:number; inner_contours:InnerContourSetting[]; attach_loop:boolean; loop_side:"top"|"bottom"|"left"|"right";
 loop_orientation:"flat"|"upright"; loop_contour_t:number|null;
 loop_position:number; loop_hole_mm:number; loop_wall_mm:number; color:string;
};
export type Plate = {
 text:string; width_mm:number; height_mm:number; thickness_mm:number;
 shape:"rounded"|"rectangle"|"oval"|"circle"|"hexagon";
 corner_radius_mm:number; top_round_mm:number;
 content_type:"text"|"image";picture:PictureSettings;
 mount_type:MountType; magnets:MagnetSettings; mount_contour_t:number|null;
 mount_side:"top"|"bottom"|"left"|"right"; mount_position:number;
 mount_hole_mm:number; mount_wall_mm:number;
 font:"sans"|"serif"|"mono"|"bold"|"russo"|"play"|"pt-sans"|"lobster"|"rubik-mono"|"unbounded"|"comfortaa"|"terminus";
 font_size_mm:number; text_align:"left"|"center"|"right"; line_spacing_mm:number;
 text_x_mm:number; text_y_mm:number;
 text_depth_mm:number; text_style:"raised"|"inlay"|"engraved";
 base_color:string; text_color:string;
};
export type BoxOptions={
 mode:"open"|"lid"|"divided";
 width_mm:number;depth_mm:number;height_mm:number;wall_mm:number;bottom_mm:number;
 corner_radius_mm:number;columns:number;rows:number;divider_mm:number;
 lid_clearance_mm:number;lid_wall_mm:number;lid_top_mm:number;lid_skirt_mm:number;
 body_color:string;lid_color:string;
};
export type Project = {id:string; name:string; kind:"silhouette"|"plate"|"box";
 updatedAt:string; silhouette?:Silhouette; plate?:Plate; box?:BoxOptions};