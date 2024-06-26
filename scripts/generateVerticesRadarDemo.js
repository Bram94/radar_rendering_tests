// import { NestedArray, slice, openArray } from "../node_modules/zarr";
// const zarr = require('zarr')(fs.readFile)

var totalVertices_before = 0;
var pos, colors, azimuths;
export async function generateVertices(url) {
  //get file from server
  const t = new Date().getTime();
  
  const z = await zarr.openArray({ store: "http://localhost:8080/", path: url, mode: "r" });
  const values = (await z.get()).data;
  
  console.log(new Date().getTime()-t, "fetch and open zarr");

  const attrs = await z.attrs.asObject();
  const azs = attrs.azimuths;
  const azmin = azs[0];
  const azmax = azs[azs.length-1];
    
  const totalVertices = values.length*(values[0].length*2+2);
  const new_pos = totalVertices != totalVertices_before;
  if (new_pos) {
    pos = new Float32Array(2*totalVertices);
    colors = new Uint8Array(totalVertices);
    azimuths = new Float32Array(azs.length);
  }

  var n = 0;  
  var i_azi_right;
  for (var i=0; i<values.length; i++) {    
    azimuths[i] = (i == 0) ? (azmin+360+azmax)/2 : (azs[i-1]+azs[i])/2;
    
    i_azi_right = (i+1) % azs.length;
    //loop through radar range gates
    for (var j=0; j<values[0].length; j++) {
      if (j == 0) {
        if (new_pos) {
          pos[2*n] = j;
          pos[2*n+1] = i;
          pos[2*n+2] = j;
          pos[2*n+3] = i_azi_right;
        }
        colors[n] = colors[n+1] = (i == 0) ? values[0][0] : 0;
        n += 2;
      }
      if (new_pos) {
        pos[2*n] = j+1;
        pos[2*n+1] = i;
        pos[2*n+2] = j+1;
        pos[2*n+3] = i_azi_right;
      }
      colors[n] = colors[n+1] = values[i][j];
      
      n += 2;
    }
  }
  totalVertices_before = totalVertices;
  
  console.log(new Date().getTime()-t, "loop");
  return { pos, colors, azimuths };
}
