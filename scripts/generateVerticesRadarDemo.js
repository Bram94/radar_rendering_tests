// import { NestedArray, slice, openArray } from "../node_modules/zarr";
// const zarr = require('zarr')(fs.readFile)

var refDataShape = [0, 0];
var pos, texpos, azimuths;
export async function generateVertices(url) {
  const t = new Date().getTime();
  
  //get file from server
  const z = await zarr.openArray({ store: "http://localhost:8080/", path: url, mode: "r" });
  const values = (await z.get()).data;
  const attrs = await z.attrs.asObject();

  console.log(new Date().getTime()-t, "fetch and open zarr");

  const nazs = attrs.nazs;
  const ngates = attrs.ngates;
  const azs = attrs.azimuths;
  const azmin = azs[0];
  const azmax = azs[azs.length-1];
    
  // It appears not needed to update the arrays when the shape of the data changes, as long as the arrays can at least contain the required number of
  // azimuths and radial gates. The vertex shaders includes the logic that prevents drawing undesired triangles.
  const update_vertices = nazs > refDataShape[0] || ngates > refDataShape[1];
  if (update_vertices) {
    const totalVertices = nazs*6;
    pos = new Float32Array(2*totalVertices);
    texpos = new Float32Array(2*totalVertices);
    azimuths = new Float32Array(nazs);
    refDataShape = [nazs, ngates];
  }

  var n = 0;  
  for (var i=0; i<nazs; i++) {
    // These azimuths are used in the vertex shader.
    azimuths[i] = (i == 0) ? (azmin+360+azmax)/2 : (azs[i-1]+azs[i])/2;
    
    if (update_vertices) {
      // The positions set here are actually indices refering to a certain azimuth or range gate. 
      // The conversion from index to actual position takes place in the vertex shader.
      pos[2*n] = 0;
      pos[2*n+1] = i;
      pos[2*n+2] = 0;
      pos[2*n+3] = i+1;
      pos[2*n+4] = ngates;
      pos[2*n+5] = i;
      pos[2*n+6] = ngates;
      pos[2*n+7] = i;
      pos[2*n+8] = ngates;
      pos[2*n+9] = i+1;
      pos[2*n+10] = 0;
      pos[2*n+11] = i+1;

      texpos[2*n] = 0;
      texpos[2*n+1] = i;
      texpos[2*n+2] = 0;
      texpos[2*n+3] = i+1;
      texpos[2*n+4] = ngates;
      texpos[2*n+5] = i;
      texpos[2*n+6] = ngates;
      texpos[2*n+7] = i;
      texpos[2*n+8] = ngates;
      texpos[2*n+9] = i+1;
      texpos[2*n+10] = 0;
      texpos[2*n+11] = i+1;
      n += 6;
    }
  }
  
  console.log(new Date().getTime()-t, "loop");
  const shape = [nazs, ngates];
  return { pos, texpos, values, azimuths, shape, update_vertices };
}