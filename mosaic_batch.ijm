/*
 * Mosaic 2D Batch Runner (Suppress Log Window)
 */

setBatchMode(true);
root = getArgument();

if (lengthOf(root) < 2) {
    echo(">>> Error: No folder argument provided.");
    run("Quit");
}
if (!endsWith(root, File.separator)) {
    root = root + File.separator;
}

echo(">>> Batch Started: " + root);
processFolder(root);
echo(">>> Batch Complete.");
run("Quit");

// Helper to print to console without opening Log window
function echo(msg) {
    js = "System.out.println(\"" + msg + "\");";
    eval("script", js);
}

function closeLogWindow() {
    if (isOpen("Log")) {
        selectWindow("Log");
        run("Close");
    }
    if (isOpen("Console")) {
        selectWindow("Console");
        run("Close");
    }
}

function processFolder(dir) {
    list = getFileList(dir);
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
    closeLogWindow(); // Keep closing it
    
    inputPath = dir + filename;
    dotIndex = lastIndexOf(filename, ".");
    baseName = substring(filename, 0, dotIndex);
    finalCSV = dir + baseName + ".csv";

    if (File.exists(finalCSV)) {
        echo(">>> Skipped (Exists): " + filename);
        return;
    }

    echo(">>> Processing: " + filename);
    
    // 1. Open Image
    run("Bio-Formats Importer", "open=[" + inputPath + "] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
    closeLogWindow();

    // 2. Run Tracker
    run("Particle Tracker 2D/3D", "radius=3 cutoff=0.001 percentile=0.5 link=2 displacement=10 dynamics=Brownian");
    closeLogWindow();

    // 3. Wait for Output
    tEnd = getTime() + 60000; 
    found = false;
    target = "";

    p1 = dir + "Traj_" + filename + ".csv";
    p2 = dir + "Traj_" + baseName + ".csv"; 

    while (getTime() < tEnd) {
        if (File.exists(p1)) { target = p1; found = true; break; }
        if (File.exists(p2)) { target = p2; found = true; break; }
        
        // Also check if Results table is open (backup)
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
            File.rename(target, finalCSV);
        }
        echo(">>> Done: " + baseName + ".csv");
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
            File.delete(dir + f);
        }
    }
}