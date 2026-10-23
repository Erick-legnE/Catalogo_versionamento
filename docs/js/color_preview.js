/* Brasil Botões — preview ilustrativa a partir de Cores1.xlsx
   A cor NÃO é RGB real/medida. Fotos reais têm prioridade.
   Não depende de backend nem de bibliotecas externas. */
(function(global){'use strict';
const UNKNOWN={kind:'unknown',palette:[],confidence:'unknown',effects:[]};
function select(code,catalog,overrides){
 const key=String(code||'').toUpperCase().replace(/\s+/g,'');
 const entry=catalog?.colors?.[key]||null;
 const base=entry?.preview||UNKNOWN;
 const ov=overrides?.colors?.[key]||null;
 const recipe=ov?{...base,...ov}:{...base};
 const text=[entry?.descricao,entry?.observacao,entry?.observacao_extra].filter(Boolean).join(' ').toUpperCase();
 const ratios=[...text.matchAll(/(\d+(?:[.,]\d+)?)\s*%/g)].map(m=>Number(m[1].replace(',','.'))).filter(Number.isFinite);
 if(!ov?.kind&&Array.isArray(recipe.palette)&&recipe.palette.length>1&&ratios.length>1&&/[\/+]/.test(text)){
   recipe.kind='layered';recipe.mix_ratios=ratios.slice(0,recipe.palette.length);recipe.method='mistura percentual ilustrativa';
 }
 return {code:key,entry,recipe,override:!!ov};
}
function depthLayers(entryOrRecipe){
 const entry=entryOrRecipe?.entry||entryOrRecipe||null;
 const recipe=entryOrRecipe?.recipe||entryOrRecipe?.preview||entryOrRecipe||UNKNOWN;
 const colors=Array.isArray(recipe.palette)&&recipe.palette.length?recipe.palette:['#58656b'];
 const text=[entry?.descricao,entry?.observacao,entry?.observacao_extra].filter(Boolean).join(' ').toUpperCase();
 const mm=[...text.matchAll(/(\d+(?:[.,]\d+)?)\s*MM\b/g)].map(m=>Number(m[1].replace(',','.'))).filter(Number.isFinite);
 const depth=Math.max(.1,Math.min(1.2,mm[0]||.2));
 let back=colors[1]||blend(colors[0],'#17232a',.42);
 let label='espessura visual estimada';
 const names=Array.isArray(recipe.color_names)?recipe.color_names:[];
 const layerMatch=text.match(/(?:FUNDO|BASE|VERSO)\s+([^/;]+)/);
 if(layerMatch&&names.length){const idx=names.findIndex(name=>layerMatch[1].includes(String(name).toUpperCase()));if(idx>=0&&colors[idx])back=colors[idx]}
 if(/FUNDO|BASE|VERSO|CAMADA/.test(text))label='fundo/camada visual estimada';
 if(recipe.kind==='border_core'&&colors[1])label='fundo visual estimado';
 return [{color:back,depthMm:depth,label,source:mm.length?'descrição com espessura':'estimativa padrão'}];
}
function randgen(text){let state=2166136261;for(let i=0;i<text.length;i++)state=Math.imul(state^text.charCodeAt(i),16777619)>>>0;return function(){state^=state<<13;state^=state>>>17;state^=state<<5;return (state>>>0)/4294967296}}
function blend(a,b,t){const ac=parseColor(a),bc=parseColor(b);return 'rgb('+ac.map((x,i)=>Math.round(x*(1-t)+bc[i]*t)).join(',')+')'}
function parseColor(hex){hex=String(hex||'#9baab5').replace('#','');if(!/^[0-9a-f]{6}$/i.test(hex))hex='9baab5';return [0,2,4].map(i=>parseInt(hex.slice(i,i+2),16))}
function weightedMix(colors,ratios){
 const weights=Array.isArray(ratios)&&ratios.length?ratios:colors.map(()=>1),total=weights.reduce((a,b)=>a+b,0)||1;
 const rgb=colors.map(parseColor);return 'rgb('+[0,1,2].map(i=>Math.round(rgb.reduce((sum,c,j)=>sum+c[i]*(weights[j]||0),0)/total)).join(',')+')';
}
function circle(ctx,x,y,r,c){ctx.beginPath();ctx.arc(x,y,Math.max(0,r),0,Math.PI*2);ctx.fillStyle=c;ctx.fill()}
function shine(ctx,x,y,r){
 const g=ctx.createRadialGradient(x-r*.42,y-r*.5,r*.08,x,y,r*1.25);
 g.addColorStop(0,'rgba(255,255,255,.24)');g.addColorStop(.48,'rgba(255,255,255,.035)');g.addColorStop(.85,'rgba(0,0,0,.025)');g.addColorStop(1,'rgba(0,0,0,.27)');
 circle(ctx,x,y,r,g);
}
function paint(ctx,x,y,r,entryOrRecipe,seed=''){
 const recipe=entryOrRecipe?.preview||entryOrRecipe||UNKNOWN;
 const p=Array.isArray(recipe.palette)?recipe.palette:[];
 const type=recipe.kind||'unknown';
 const colors=p.length?p:['#c0c7cc','#84939d'];
 const rnd=randgen(String(seed||'')).bind(null);
 ctx.save();ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.clip();
 const fill=(c,ratio=1)=>circle(ctx,x,y,r*ratio,c);
 if(type==='unknown'){
   fill('#dce4e7');
   ctx.save();ctx.strokeStyle='rgba(90,110,120,.13)';ctx.lineWidth=Math.max(1,r*.022);
   for(let i=-r*3;i<r*3;i+=r*.15){ctx.beginPath();ctx.moveTo(x-r+i,y+r);ctx.lineTo(x+r+i,y-r);ctx.stroke()}ctx.restore();
   ctx.fillStyle='rgba(53,72,85,.6)';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`900 ${Math.round(r*.5)}px sans-serif`;ctx.fillText('?',x,y);
 }else if(type==='border_core'){
   fill(colors[0]);
   // This ring is an illustrative color relationship, not a measured border thickness.
   fill(colors[1]||'#d9d5c8',.77);
   if(colors[2])fill(colors[2],.47);
 }else if(type==='layered'){
   if(Array.isArray(recipe.mix_ratios)&&recipe.mix_ratios.length>1){
    fill(weightedMix(colors,recipe.mix_ratios));
    ctx.globalAlpha=.16;
    for(let i=0;i<Math.min(colors.length,5);i++)fill(colors[i],.82-i*.08);
    ctx.globalAlpha=1;
   }else{
    fill(colors[0]);
    for(let i=1;i<Math.min(colors.length,5);i++)fill(colors[i],1-i/(colors.length+.5));
   }
 }else if(type==='transparent'){
   fill('#e0e6df');
   const grd=ctx.createLinearGradient(x-r,y-r,x+r,y+r);grd.addColorStop(0,'rgba(255,255,255,.76)');grd.addColorStop(.6,'rgba(255,255,255,.10)');grd.addColorStop(1,'rgba(93,140,151,.18)');fill(grd);
 }else if(type==='gradient'){
   const gradient=ctx.createLinearGradient(x-r*.8,y-r*.7,x+r*.8,y+r*.7);
   let cc=colors.length>=2?colors:[colors[0],blend(colors[0],'#f9f6ed',.55)];
   cc.forEach((c,i)=>gradient.addColorStop(i/(cc.length-1),c));fill(gradient);
 }else{
   fill(colors[0]);
   if(type==='wood'){
     ctx.lineCap='round';for(let i=0;i<30;i++){
       const dy=(rnd()*2-1)*r; const off=(rnd()*2-1)*r*.23;
       ctx.strokeStyle=i%3===0?blend(colors[0],colors[1]||'#533624',.6):'rgba(255,241,215,.15)';
       ctx.lineWidth=r*(.008+rnd()*.028);ctx.beginPath();
       for(let j=0;j<8;j++){let xx=x-r+j*2*r/7;let yy=y+dy+Math.sin(j*.6+off)*r*.044; j?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy)}ctx.stroke()
     }
   }else if(type==='tortoise'||type==='marble'){
     const alt=colors.length>1?colors.slice(1):[blend(colors[0],'#eee5d2',.5),'#342b29'];
     for(let i=0;i<(type==='tortoise'?55:115);i++){
       let xx=x+(rnd()*2-1)*r, yy=y+(rnd()*2-1)*r;
       const rr=r*(.06+rnd()*(type==='tortoise'?.28:.20));
       ctx.globalAlpha=.15+rnd()*.57;ctx.fillStyle=alt[Math.floor(rnd()*alt.length)];
       ctx.beginPath();ctx.ellipse(xx,yy,rr,rr*(.25+rnd()*.65),rnd()*Math.PI,0,Math.PI*2);ctx.fill();
     }
     ctx.globalAlpha=.30;ctx.lineWidth=Math.max(1,r*.01);
     for(let i=0;i<22;i++){
       const yy=y+(rnd()*2-1)*r,xx=x+(rnd()*2-1)*r;
       ctx.strokeStyle=alt[Math.floor(rnd()*alt.length)];ctx.beginPath();ctx.moveTo(xx-r*.15,yy);
       ctx.bezierCurveTo(xx-r*.1,yy-r*.12,xx+r*.1,yy+r*.11,xx+r*.3,yy-r*.07);ctx.stroke()
     }ctx.globalAlpha=1;
   }
 }
 if(recipe.effects?.includes('glitter')||recipe.effects?.includes('iridescent')){
   ctx.globalAlpha=.65;for(let i=0;i<65;i++){
     let xx=x+(rnd()*2-1)*r,yy=y+(rnd()*2-1)*r;
     ctx.fillStyle=rnd()>.6?'#f5e4bc':'#ffffff';circle(ctx,xx,yy,r*(.003+rnd()*.011),ctx.fillStyle)
   }ctx.globalAlpha=1;
 }
 if(recipe.effects?.includes('translucent')){
   const g=ctx.createLinearGradient(x-r,y-r,x+r,y+r);
   g.addColorStop(0,'rgba(255,255,255,.24)');g.addColorStop(1,'rgba(225,242,246,.10)');fill(g)
 }
 shine(ctx,x,y,r);
 ctx.restore();
 ctx.save();ctx.strokeStyle='rgba(29,39,46,.28)';ctx.lineWidth=Math.max(.9,r*.012);ctx.beginPath();ctx.arc(x,y,r-.8,0,Math.PI*2);ctx.stroke();ctx.restore();
}
function drawButton(canvas,entry,pattern,seed){
 const ctx=canvas.getContext('2d'),W=canvas.width,H=canvas.height,r=Math.min(W,H)*.40,cx=W/2,cy=H/2;
 ctx.clearRect(0,0,W,H);drawButton3D(ctx,cx,cy,r,entry,seed||'button');
 if(pattern)drawHoles(ctx,cx,cy,r,pattern);
}
function drawButton3D(ctx,x,y,r,entryOrRecipe,seed='button'){
 const recipe=entryOrRecipe?.preview||entryOrRecipe||UNKNOWN;
 const layers=depthLayers(entryOrRecipe);
 const depthPx=Math.max(3,Math.min(r*.16,layers[0].depthMm*r*.34));
 const ox=-depthPx*.72,oy=-depthPx;
 const back=layers[0];
 const steps=Math.max(4,Math.ceil(depthPx/2));
 for(let i=steps;i>=1;i--){
  const t=i/steps,cx=x+ox*t,cy=y+oy*t;
  circle(ctx,cx,cy,r,back.color);
  ctx.save();ctx.strokeStyle='rgba(20,30,34,.25)';ctx.lineWidth=Math.max(.8,r*.012);ctx.beginPath();ctx.arc(cx,cy,r-.8,0,Math.PI*2);ctx.stroke();ctx.restore();
 }
 paint(ctx,x,y,r,entryOrRecipe,seed);
}
function drawHoles(ctx,x,y,r,pattern){
 const points=pattern?.points||[];
 if(points.length>18)return;
 const rr=Math.min(Math.max(Number(pattern.hole_radius_ratio)||.08,.025),.16)*r;
 for(const pt of points){
  const px=Array.isArray(pt)?pt[0]:pt.x,py=Array.isArray(pt)?pt[1]:pt.y;
  if(!Number.isFinite(px)||!Number.isFinite(py))continue;
  const cx=x+px*r,cy=y+py*r;
  circle(ctx,cx+rr*.12,cy+rr*.1,rr*1.1,'rgba(255,255,255,.25)');
  const g=ctx.createRadialGradient(cx-rr*.25,cy-rr*.25,rr*.1,cx,cy,rr);g.addColorStop(0,'#222e37');g.addColorStop(.68,'#17232a');g.addColorStop(1,'#09141e');circle(ctx,cx,cy,rr,g)
 }
}
global.BBColorPreview={select,paint,drawButton,drawButton3D,depthLayers,drawHoles};
})(window);
