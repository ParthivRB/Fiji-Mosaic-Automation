// Silent headless Mosaic 2D runner
// Saves ONLY <samebasename>.csv, deletes Traj_* leftovers,
// and QUITS Fiji only after the folder is clean.

setBatchMode(true);  // suppress UI

function q(s){
  s = trim(s);
  if (startsWith(s,"'"))  s = substring(s,1);
  if (endsWith(s,"'"))    s = substring(s,0,lengthOf(s)-1);
  if (startsWith(s,"\"")) s = substring(s,1);
  if (endsWith(s,"\""))   s = substring(s,0,lengthOf(s)-1);
  return s;
}

function parse(arg){
  inp = ""; outp = "";
  parts = split(arg, ","); // split ONLY on commas
  for (i=0; i<parts.length; i++){
    kv = trim(parts[i]);
    if (startsWith(kv,"input="))  inp  = q(substring(kv,6));
    if (startsWith(kv,"output=")) outp = q(substring(kv,7));
  }
  return newArray(inp, outp);
}

function parentDir(p){
  i = lastIndexOf(p, "/");
  if (i < 0) return "";
  return substring(p, 0, i+1);
}

function baseNoExt(p){
  i = lastIndexOf(p, "/");
  if (i >= 0) name = substring(p, i+1); else name = p;
  j = lastIndexOf(name, ".");
  if (j > 0) name = substring(name, 0, j);
  return name;
}

function pickTable(){
  t = getList("window.titles");
  cand = newArray("All Trajectories","Trajectories","Results Table","Results");
  for (c=0; c<cand.length; c++)
    for (i=0; i<t.length; i++)
      if (t[i] == cand[c]) { selectWindow(t[i]); return t[i]; }
  for (i=0; i<t.length; i++){
    w = t[i]; L = toLowerCase(w);
    if (indexOf(L,"trajec")>=0 || indexOf(L,"result")>=0 || indexOf(L,"table")>=0){
      selectWindow(w); return w;
    }
  }
  return "";
}

// Count Traj_* files for this image in dir
function countTraj(dir, base){
  files = getFileList(dir);
  n = 0;
  for (k=0; k<files.length; k++){
    nm = toLowerCase(files[k]);
    if ((endsWith(nm,".csv") || endsWith(nm,".txt")) && startsWith(nm,"traj_") && indexOf(nm,base)>=0) n++;
  }
  return n;
}

// Move best Traj_* to outPath; delete all other Traj_* for this image
function adoptAndClean(dir, base, outPath){
  bestCsv = ""; bestTxt = "";
  files = getFileList(dir);
  for (k=0; k<files.length; k++){
    nm = files[k]; L = toLowerCase(nm);
    if ((endsWith(L,".csv") || endsWith(L,".txt")) && startsWith(L,"traj_") && indexOf(L,base)>=0){
      if (endsWith(L,".csv")) bestCsv = dir + nm;
      if (endsWith(L,".txt")) bestTxt = dir + nm;
    }
  }
  src = "";
  if (bestCsv != "") src = bestCsv; else if (bestTxt != "") src = bestTxt;
  if (src != ""){
    if (File.exists(outPath)) File.delete(outPath);
    ok = File.rename(src, outPath);
    if (!ok){ File.copy(src, outPath); File.delete(src); }
  }
  // delete any remaining Traj_* remnants
  files = getFileList(dir);
  for (k=0; k<files.length; k++){
    nm = files[k]; L = toLowerCase(nm);
    if ((endsWith(L,".csv") || endsWith(L,".txt")) && startsWith(L,"traj_") && indexOf(L,base)>=0){
      f = dir + nm; if (f != outPath) File.delete(f);
    }
  }
}

// Wait until: CSV exists AND no Traj_* left (or timeout)
function waitUntilClean(dir, base, outPath, timeoutMs){
  end = getTime() + timeoutMs;
  stableSeen = 0;
  while (getTime() < end){
    haveCsv = File.exists(outPath);
    ntraj   = countTraj(dir, base);
    if (!haveCsv && ntraj > 0) adoptAndClean(dir, base, outPath);
    else if (haveCsv && ntraj > 0) adoptAndClean(dir, base, outPath);

    haveCsv = File.exists(outPath);
    ntraj   = countTraj(dir, base);

    if (haveCsv && ntraj == 0){
      stableSeen++;
      if (stableSeen >= 2) return; // two consecutive clean checks
    } else {
      stableSeen = 0;
    }
    wait(200);
  }
}

// -------------------- main --------------------
arg = getArgument(); A = parse(arg);
input  = A[0];
output = A[1];

if (input=="" || output==""){
  call("ij.WindowManager.closeAllWindows"); run("Close All"); setBatchMode(false); run("Quit"); return;
}

dir  = parentDir(input);
base = toLowerCase(baseNoExt(input));

// Import + run tracker
run("Bio-Formats Windowless Importer", "open=[" + input + "]");
run("Particle Tracker 2D/3D",
    "radius=3 cutoff=0.001 percentile=0.5 link=2 displacement=10 dynamics=Brownian");

// Try to save table (up to 15s)
tEnd = getTime() + 15000; sel = "";
while (sel=="" && getTime()<tEnd){ wait(250); sel = pickTable(); }
if (sel!=""){
  if (sel=="Results" || sel=="Results Table") saveAs("Results", output);
  else saveAs("Text", output);
  wait(300);
}

// Ensure final state: CSV present, no Traj_* leftovers, then quit
waitUntilClean(dir, base, output, 8000);

// Close everything and QUIT (now safe — output is ready and clean)
call("ij.WindowManager.closeAllWindows");
run("Close All");
setBatchMode(false);
run("Quit");
