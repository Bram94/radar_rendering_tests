// import { NestedArray, slice, openArray } from "../node_modules/zarr";
// const zarr = require('zarr')(fs.readFile)

var refDataShape = [0, 0];
var pos, texpos, azimuths;
export async function generateVertices(url) {
  //get file from server
  const t = new Date().getTime();
  
  const z = await zarr.openArray({ store: "http://localhost:8080/", path: url, mode: "r" });
  const values = (await z.get()).data;
  
  console.log(new Date().getTime()-t, "fetch and open zarr");

  const attrs = await z.attrs.asObject();
  const nazs = attrs.nazs;
  const ngates = attrs.ngates;
  const azs = attrs.azimuths;
  const azmin = azs[0];
  const azmax = azs[azs.length-1];
    
  const totalVertices = nazs*(ngates*2+4);
  // It appears not needed to update the arrays when the shape of the data changes, as long as the arrays can at least contain the required number of
  // azimuths and radial gates. The vertex shaders includes the logic that prevents drawing undesired triangles.
  const update_vertices = nazs > refDataShape[0] || ngates > refDataShape[1];
  if (update_vertices) {
    pos = new Float32Array(2*totalVertices);
    texpos = new Float32Array(2*totalVertices);
    azimuths = new Float32Array(nazs);
    refDataShape = [nazs, ngates];
  }

  var n = 0;  
  for (var i=0; i<nazs; i++) {    
    azimuths[i] = (i == 0) ? (azmin+360+azmax)/2 : (azs[i-1]+azs[i])/2;
    
    if (update_vertices) {
      for (var j=0; j<ngates; j++) {
        if (j == 0) {
          pos[2*n] = j;
          pos[2*n+1] = i;
          pos[2*n+2] = j;
          pos[2*n+3] = i+1;
          texpos[2*n] = texpos[2*n+2] = j;
          texpos[2*n+1] = texpos[2*n+3] = i;
          n += 2;
        }
        pos[2*n] = j+1;
        pos[2*n+1] = i;
        pos[2*n+2] = j+1;
        pos[2*n+3] = i+1;
        texpos[2*n] = texpos[2*n+2] = j;
        texpos[2*n+1] = texpos[2*n+3] = i;
        n += 2;
        if (j == ngates-1) {
          pos[2*n] = j+1;
          pos[2*n+1] = i+1;
          pos[2*n+2] = 0;
          pos[2*n+3] = i+1;
          texpos[2*n] = j;
          texpos[2*n+1] = i;
          texpos[2*n+2] = 0;
          texpos[2*n+3] = i+1;
          n += 2;
        }
      }
    }
  }
  
  console.log(new Date().getTime()-t, "loop");
  const shape = [nazs, ngates];
  return { pos, texpos, values, azimuths, shape, update_vertices };
}