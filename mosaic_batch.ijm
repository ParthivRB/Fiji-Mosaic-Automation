/*
 * Mosaic 2D Batch - Flattened List Strategy
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

// 1. Build a massive flat list of ALL files first (Solves recursion bug)
allFiles = getAllFiles(root);
count = allFiles.length;

if (count == 0) {
    echo(">>> Error: No OIR files found.");
    eval("script", "System.exit(0);");
}

// 2. Shuffle the flat list
randoms = newArray(count);
for (k=0; k<count; k++) randoms[k] = random();

for (i=0; i<count; i++) {
    for (j=1; j<count-i; j++) {
        if (randoms[j-1] > randoms[j]) {
            t = randoms[j-1]; randoms[j-1] = randoms[j]; randoms[j] = t;
            tStr = allFiles[j-1]; allFiles[j-1] = allFiles[j]; allFiles[j] = tStr;
        }
    }
}

// 3. Process the shuffled list
for (i = 0; i < count; i++) {
    processFile(allFiles[i]);
}

// Force Quit
eval("script", "System.exit(0);");

// ---------------------------------------------------------

// Recursive crawler that returns a flat array of file paths
function getAllFiles(dir) {
    fileList = newArray(0);
    list = getFileList(dir);
    
    for (i = 0; i < list.length; i++) {
        if (endsWith(list[i], "/")) {
            // Recurse
            subList = getAllFiles(dir + list[i]);
            fileList = Array.concat(fileList, subList);
        } else if (endsWith(toLowerCase(list[i]), ".oir")) {
            // Add full path
            fileList = Array.concat(fileList, dir + list[i]);
        }
    }
    return fileList;
}

function echo(msg) {
    js = "System.out.println(\"" + msg + "\");";
    eval("script", js);
}

function closeLogWindow() {
    if (isOpen("Log")) { selectWindow("Log"); run("Close"); }
    if (isOpen("Console")) { selectWindow("Console"); run("Close"); }
    if (isOpen("Exception")) { selectWindow("Exception"); run("Close"); }
}

function processFile(fullPath) {
    closeLogWindow();
    
    // Extract directory and filename from full path
    lastSlash = lastIndexOf(fullPath, File.separator);
    dir = substring(fullPath, 0, lastSlash + 1);
    filename = substring(fullPath, lastSlash + 1);
    
    dotIndex = lastIndexOf(filename, ".");
    baseName = substring(filename, 0, dotIndex);
    finalCSV = dir + baseName + ".csv";

    if (File.exists(finalCSV)) return; 

    echo(">>> Processing: " + filename);
    
    run("Bio-Formats Importer", "open=[" + fullPath + "] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT windowless=true");
    closeLogWindow();
    setOption("Changes", false);

    run("Particle Tracker 2D/3D", "radius=3 cutoff=0.001 percentile=0.5 link=2 displacement=10 dynamics=Brownian");
    closeLogWindow();

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