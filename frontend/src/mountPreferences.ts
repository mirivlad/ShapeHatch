export type MountPreferences = {holeMm:number; wallMm:number};
const KEY = "shapehatch.mount-defaults.v1";
export const DEFAULT_MOUNT:MountPreferences = {holeMm:5,wallMm:2.3};

export function loadMountPreferences():MountPreferences {
 try {
  const raw = localStorage.getItem(KEY);
  if (!raw) return {...DEFAULT_MOUNT};
  const value = JSON.parse(raw) as Partial<MountPreferences>;
  const hole = Number(value.holeMm), wall = Number(value.wallMm);
  return {
   holeMm:Number.isFinite(hole)&&hole>=2&&hole<=12?hole:DEFAULT_MOUNT.holeMm,
   wallMm:Number.isFinite(wall)&&wall>=1&&wall<=6?wall:DEFAULT_MOUNT.wallMm,
  };
 } catch {return {...DEFAULT_MOUNT};}
}

export function storeMountPreferences(value:MountPreferences):void {
 try {localStorage.setItem(KEY,JSON.stringify(value));}
 catch {/* Private mode or disabled storage: continue without persistence. */}
}
