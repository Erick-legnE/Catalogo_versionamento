(function(global){'use strict';
function resolve(reference,tam,patterns,map){
 const ref=String(reference||'').replace(/^0+(?=\d)/,'');const size=String(tam||'');
 const cfg=map?.refs?.[ref]?.by_size?.[size];
 const key=cfg?.pattern||'four_square';
 const base=patterns?.patterns?.[key]||patterns?.patterns?.four_square||{points:[]};
 // Based on relative spacing in historical technical data; not precise engineering coordinates.
 const spacing=Number(cfg?.visual_spacing_scale)||1;
 const drill=Number(cfg?.visual_drill_scale)||1;
 const pattern={...base,points:(base.points||[]).map(p=>Array.isArray(p)?[p[0]*spacing,p[1]*spacing]:{...p,x:p.x*spacing,y:p.y*spacing}),
 hole_radius_ratio:Math.min(.14,Math.max(.035,(base.hole_radius_ratio||.08)*drill))};
 return {key,pattern,verifiedCount:!!cfg,count:cfg?.count??null,spacingMillimeters:cfg?.distancia_furos_mm??null,
     drillMillimeters:cfg?.broca_mm??null,exactPositionsVerified:false};
}
global.BBHoles={resolve};
})(window);
