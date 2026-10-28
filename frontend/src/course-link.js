export function courseLink({stops,startPoint,maxMinutes,returnLeg,locale,scheduleStart,departureDate}) {
  const params=new URLSearchParams({start:`${startPoint.lat},${startPoint.lon}`,minutes:String(maxMinutes),return:returnLeg?"1":"0",lang:locale});
  stops.forEach(stop=>params.append("stop",stop.id));
  if(scheduleStart) params.set("depart",scheduleStart);
  if(departureDate) params.set("date",departureDate);
  if(startPoint.label && startPoint.label!=="내 위치") params.set("label",startPoint.label);
  return `${window.location.origin}/?${params}`;
}
