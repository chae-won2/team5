// Ignore responses for old map centers and stop requests when the map unmounts.
export function watchMapRegion(map, lookup, onChange) {
  let timer, controller, generation = 0;
  function update() {
    const current = ++generation;
    clearTimeout(timer);
    controller?.abort();
    onChange({status:"loading",label:""});
    timer = setTimeout(async () => {
      const {lat,lng} = map.getCenter();
      const request = new AbortController();
      controller = request;
      try {
        const region = await lookup({lat,lon:lng,signal:request.signal});
        if (current === generation && !request.signal.aborted) onChange({status:"ready",label:[region.district,region.dong].filter(Boolean).join(" ")});
      } catch (error) {
        if (current === generation && !request.signal.aborted && error.name !== "AbortError") onChange({status:"error",label:""});
      }
    },350);
  }
  map.on("moveend",update);
  update();
  return () => { generation++; clearTimeout(timer); controller?.abort(); map.off("moveend",update); };
}
