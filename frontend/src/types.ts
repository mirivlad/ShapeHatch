export type Section = "home" | "silhouette" | "plate" | "gallery";
export type Vec3 = [number,number,number];
export type Part = { name:string; color:string; vertices:Vec3[]; faces:Vec3[] };
export type Preview = { parts:Part[]; size_mm:number[]; warnings:string[];
 mount_contour:number[][]; mount_fraction:number|null; mount_surface_z:number };
export type Silhouette = {
 image_data:string; filename:string; width_mm:number; thickness_mm:number;
 threshold:number; invert:boolean; mode:"filled"|"cutouts"|"lines";
 smoothing_mm:number; attach_loop:boolean; loop_side:"top"|"bottom"|"left"|"right";
 loop_orientation:"flat"|"upright"; loop_contour_t:number|null;
 loop_position:number; loop_hole_mm:number; loop_wall_mm:number; color:string;
};
export type Plate = {
 text:string; width_mm:number; height_mm:number; thickness_mm:number;
 shape:"rounded"|"rectangle"|"oval"|"circle"|"hexagon";
 corner_radius_mm:number; mount_type:"none"|"hole"|"loop"|"upright"; mount_contour_t:number|null;
 mount_side:"top"|"bottom"|"left"|"right"; mount_position:number;
 mount_hole_mm:number; mount_wall_mm:number;
 font:"sans"|"serif"|"mono"|"bold";
 font_size_mm:number; text_align:"left"|"center"|"right"; line_spacing_mm:number;
 text_x_mm:number; text_y_mm:number;
 text_depth_mm:number; text_style:"raised"|"inlay"|"engraved";
 base_color:string; text_color:string;
};
export type Project = {id:string; name:string; kind:"silhouette"|"plate"; updatedAt:string; silhouette?:Silhouette; plate?:Plate};
