// import { NestedArray, slice, openArray } from "../node_modules/zarr";
// const zarr = require('zarr')(fs.readFile)

export async function generateVertices(url) {
  //get file from server
  const t = new Date().getTime();
  
  const z = await zarr.openArray({ store: "http://localhost:8080/", path: url, mode: "r" });
  const values = (await z.get()).data;
  // console.log(values.data);
  
  console.log(new Date().getTime()-t, "fetch and open zarr");

  const attrs = await z.attrs.asObject();
  const firstGate = attrs.first_gate;
  const gateRes = attrs.gate_spacing;
  const ngates = attrs.ngates;
  const azs = attrs.azimuths;
  const min = azs[0];
  const max = azs[azs.length-1];
    
  const totalVertices = values.length*(values[0].length*2+2);
  var pos = new Float32Array(2*totalVertices);
  var colors = new Uint8Array(totalVertices);

  const ranges = new Float32Array([...Array(ngates).keys()]).map(x => firstGate + gateRes*x);
  var n = 0;
  var az, leftAz, rightAz, bottomR, topR;
  
  for (var key in values) {
    key = +key;
    az = azs[key];

    //case when first az
    if (key == 0) {
      //case when crossing 0
      leftAz = (min + 360 + max)/2;
      rightAz = (az+azs[key+1])/2;
    } else if (key == azs.length-1) {
      //case when crossing 0 the other way
      leftAz = (az + azs[key-1])/2;
      rightAz = (min+360+max)/2;
    } else {
      //case when nothing to worry about
      leftAz = (az + azs[key-1])/2;
      rightAz = (az + azs[key+1])/2;
    }
    
    //loop through radar range gates
    for (var i=0; i<values[0].length; i++) {
      bottomR = ranges[i] - gateRes/2;
      topR = ranges[i] + gateRes/2;
      
      if (i == 0) {
        pos[2*n] = bottomR;
        pos[2*n+1] = leftAz;
        pos[2*n+2] = bottomR;
        pos[2*n+3] = rightAz;
        if (key == 0) {
          colors[n] = colors[n+1] = values[0][0];
        } else {
          colors[n] = colors[n+1] = 0;
        }
        n += 2;
      }
      
      pos[2*n] = topR;
      pos[2*n+1] = leftAz;
      pos[2*n+2] = topR;
      pos[2*n+3] = rightAz;
      colors[n] = colors[n+1] = values[key][i];
      
      n += 2;
    }
  }
  
  const repeat = (arr, n) => Array(n).fill(arr).flat();
  console.log(repeat([1,2], 3));
  
  console.log(new Date().getTime()-t, "loop");
  return { pos, colors };
}
