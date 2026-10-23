import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';
const { finalizePresentation } = await import(pathToFileURL('C:/Users/Aprendiz Financeiro/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations/container_tools/artifact_tool_utils.mjs').href);

const workspaceDir = 'C:/Users/Aprendiz Financeiro/Downloads/Erick/site';
const build = path.join(workspaceDir, '.codex-build');
const finalPath = path.join(workspaceDir, 'output/presentations/projeto_brasil_botoes.pptx');
const font = 'Aptos';
const deck = Presentation.create({slideSize:{width:1280,height:720}});
const addText=(s,text,left,top,width,height,size=22,color='1F2937',bold=false)=>{const x=s.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'none',line:{style:'solid',fill:'none',width:0}});x.text=text;x.text.style={fontFamily:font,fontSize:size,color,bold};return x};
const title=(s,text,sub='')=>{s.background.fill='F7F8FA';addText(s,text,72,54,900,54,34,'163C4B',true);if(sub)addText(s,sub,74,111,900,34,16,'52616B');};
const addImage=async(s,file,left,top,width,height)=>{const b=await fs.readFile(file);s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:'Button preview',fit:'contain',position:{left,top,width,height}});};

let s=deck.slides.add();s.background.fill='163C4B';addText(s,'Brasil Botões',72,82,600,70,48,'FFFFFF',true);addText(s,'Fluxo de desenvolvimento, personalização e liberação',76,166,580,80,25,'D9F3F5');addText(s,'Catálogo • Consistem • Blender • Ficha Técnica',76,590,620,30,18,'8DE4EA');await addImage(s,path.join(workspaceDir,'versions/planner-pass-2026-10-19/blender/button_13646_18_personalizado_ana_front.png'),720,80,470,530);

s=deck.slides.add();title(s,'Fluxo de trabalho','A mesma referência acompanha cadastro, modelo 3D e Ficha Técnica');
['1  Cadastro\nReferência, TAM, cor, faca e furação no Consistem','2  Modelo 3D\nGeração versionada a partir da linha validada','3  Personalização\nNome, texto ou arte em arquivo derivado','4  Liberação\nFicha revisada, consistência e aprovação'].forEach((t,i)=>{const x=80+i*292;s.shapes.add({geometry:'roundRect',position:{left:x,top:235,width:250,height:240},fill:i===3?'00B8C9':'FFFFFF',line:{style:'solid',fill:'D6D9D9',width:1},borderRadius:'rounded-xl'});addText(s,t,x+22,265,208,170,20,i===3?'FFFFFF':'26343B',false);});

s=deck.slides.add();title(s,'Operação diária');addText(s,'• Consultar o catálogo para confirmar referência, TAM e cor\n\n• Gerar o botão 3D pelo Consistem e guardar a proveniência\n\n• Criar a versão personalizada sem substituir o `.blend` base\n\n• Gerar a Ficha e executar a checagem de consistência\n\n• Guardar PDF, preview e arquivos `.blend` juntos em `versions/`',95,180,760,400,24,'26343B');await addImage(s,path.join(workspaceDir,'versions/planner-pass-2026-10-19/blender/button_13646_18_personalizado_image_front.png'),890,180,290,330);

s=deck.slides.add();title(s,'Liberação de produção','Critérios objetivos antes de enviar o item para produção');
['Linha do Consistem encontrada e validada','Facas e geometria registradas na proveniência','Ficha sem divergência de TAM, espessura ou furação','Arte aprovada na área permitida','Versão anterior preservada e responsável identificado'].forEach((t,i)=>{s.shapes.add({geometry:'ellipse',position:{left:100,top:170+i*75,width:34,height:34},fill:'00B8C9',line:{style:'solid',fill:'00B8C9',width:1}});addText(s,'✓',108,173+i*75,20,25,18,'FFFFFF',true);addText(s,t,155,174+i*75,900,30,24,'26343B');});addText(s,'Não liberar se houver dado técnico pendente ou arte raster que exija vetor para gravação.',100,600,1000,45,19,'9A3412',true);

await fs.mkdir(build,{recursive:true});await fs.mkdir(path.dirname(finalPath),{recursive:true});
const candidate=path.join(build,'projeto_brasil_botoes_candidate.pptx');await (await PresentationFile.exportPptx(deck)).save(candidate);
await finalizePresentation({workspaceDir,candidatePath:candidate,finalPath,pythonExecutable:'C:/Users/Aprendiz Financeiro/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:'C:/Users/Aprendiz Financeiro/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:'C:/Users/Aprendiz Financeiro/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(build,'projeto_brasil_botoes.validation.json')});
console.log(finalPath);
