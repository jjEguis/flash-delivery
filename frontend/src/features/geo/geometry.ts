export type Coordinate = [number, number];
export const meters = (a: Coordinate, b: Coordinate) => Math.hypot((b[0]-a[0])*111195*Math.cos((a[1]+b[1])*Math.PI/360), (b[1]-a[1])*111195);
export function along(coordinates: Coordinate[], distance: number) {
  let left = Math.max(0,distance);
  for (let i=0; i<coordinates.length-1; i++) {
    const a=coordinates[i], b=coordinates[i+1], length=meters(a,b);
    if (left<=length || i===coordinates.length-2) {
      const fraction=length ? Math.min(1,left/length) : 0;
      return {coordinate:[a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction] as Coordinate,
        index:i, heading:(Math.atan2((b[0]-a[0])*Math.cos(a[1]*Math.PI/180),b[1]-a[1])*180/Math.PI+360)%360};
    }
    left-=length;
  }
  return {coordinate:coordinates[0], index:0, heading:0};
}
export const totalMeters = (coordinates: Coordinate[]) => coordinates.slice(1).reduce((sum,p,i)=>sum+meters(coordinates[i],p),0);
