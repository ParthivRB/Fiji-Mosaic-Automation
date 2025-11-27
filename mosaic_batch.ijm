/*
 * Mosaic 2D Batch - Randomized & Self-Terminating
 * Arguments: "FolderPath|RandomSeed"
 */

setBatchMode(true);
setOption("JFileChooser", false); 

rawArgs = getArgument();
parts = split(rawArgs, "|");

if (parts.length < 2) {
    echo(">>> Error: Invalid args.");
    // Force exit java to prevent hanging
    eval("script", "System.exit(0);");
}

root = parts[0];
seed = parseInt(parts[1]);

if (!endsWith(root, File.separator)) {
    root = root + File.separator;
}

// Seed the random generator
random("seed", seed);

echo(">>> Worker Started");

processFolder(root);

// FORCE QUIT JAVA: This ensures the process actually dies so Python knows we are done.
eval("script", "System.exit(0);");

// ---------------------------------------------------------

function echo(msg) {
    js = "System.out.println(\"" + msg + "\");";
    eval("script", js);
}

function closeLogWindow() {
    if (isOpen("Log")) { selectWindow("Log"); run("Close"); }
    if (isOpen("Console")) { selectWindow("Console"); run("Close"); }
    if (isOpen("Exception")) { selectWindow("Exception"); run("Close"); }
}

function processFolder(dir) {
    list = getFileList(dir);
    
    // --- RANDOM SHUFFLE ---
    count = list.length;
    randoms = newArray(count);
    for (k=0; k<count; k++) {
        randoms[k] = random();
    }
    
    for (i=0; i<count; i++) {
        for (j=1; j<count-i; j++) {
            if (randoms[j-1] > randoms[j]) {
                t = randoms[j-1];
                randoms[j-1] = randoms[j];
                randoms[j] = t;
                tStr = list[j-1];
                list[j-1] = list[j];
                list[j] = tStr;
            }
        }
    }
    // ---------------------------

    for (i = 0; i < list.length; i++) {
        item = list[i];
        path = dir + item;
        
        if (endsWith(item, File.separator)) {
            processFolder(path);
        } else if (endsWith(toLowerCase(item), ".oir")) {
            processFile(dir, item);
        }
    }
}

function processFile(dir, filename) {
    closeLogWindow();
    
    inputPath = dir + filename;
    dotIndex = lastIndexOf(filename, ".");
    baseName = substring(filename, 0, dotIndex);
    finalCSV = dir + baseName + ".csv";

    if (File.exists(finalCSV)) return; 

    echo(">>> Processing: " + filename);
    
    run("Bio-Formats Importer", "open=[" + inputPath + "] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT windowless=true");
    closeLogWindow();
    setOption("Changes", false);

    run("Particle Tracker 2D/3D", "radius=3 cutoff=0.001 percentile=0.5 link=2 displacement=10 dynamics=Brownian");
    closeLogWindow();

    // Wait for Output (120s timeout)
    tEnd = getTime() + 120000; 
    found = false;
    target = "";

    p1 = dir + "Traj_" + filename + ".csv";
    p2 = dir + "Traj_" + baseName + ".csv"; 

    while (getTime() < tEnd) {
        if (File.exists(p1)) { target = p1; found = true; break; }
        if (File.exists(p2)) { target = p2; found = true; break; }
        
        if (isOpen("Results") || isOpen("Results Table")) {
            if (isOpen("Results")) selectWindow("Results");
            else selectWindow("Results Table");
            saveAs("Results", finalCSV);
            found = true;
            target = "SAVED_MANUALLY";
            break;
        }
        wait(500);
    }

    close("*");
    closeLogWindow();

    if (found) {
        if (target != "SAVED_MANUALLY") {
            if (File.exists(target)) {
                File.rename(target, finalCSV);
            }
        }
        if (File.exists(finalCSV)) {
            echo(">>> Done: " + baseName + ".csv");
        }
    } else {
        echo(">>> Error: Output not generated for " + filename);
    }
    
    cleanJunk(dir, baseName);
    run("Collect Garbage");
}

function cleanJunk(dir, baseName) {
    flist = getFileList(dir);
    for (k=0; k<flist.length; k++) {
        f = flist[k];
        if (startsWith(f, "Traj_") && indexOf(f, baseName) >= 0) {
            path = dir + f;
            if (path != dir + baseName + ".csv") {
                File.delete(path);
            }
        }
    }
}