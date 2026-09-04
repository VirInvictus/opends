/*
 * OvrExport.java — the text export half of the Ghidra pipeline
 * (docs/dsun-exe-re.md 8, Phase 5.6.0). Checked in (not generated):
 * it is static, catalogue-independent, and works on any program.
 *
 * Writes every function the analysis knows as one TSV line per row:
 *
 *   <entry address>  <name>  <body bytes>
 *
 * Addresses print in the program's own address space, so resident
 * functions read as seg:off and overlay functions carry their
 * synthetic overlay base (see OvrMap.java for the block comments that
 * map those back to file offsets). Pass the output path as the first
 * script argument; it defaults to functions.txt in the working
 * directory. Pair with OvrMap.java + OvrRename.java post-scripts:
 *
 *   analyzeHeadless <dir> <proj> -import DSUN.EXE \
 *       -postScript OvrMap.java -postScript OvrRename.java \
 *       -postScript OvrExport.java /abs/path/functions.txt
 *
//@category OpenDS
import java.io.FileWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

public class OvrExport extends GhidraScript {

    @Override
    public void run() throws Exception {
        String out = getScriptArgs().length > 0 ? getScriptArgs()[0] : "functions.txt";
        FileWriter w = new FileWriter(out);
        w.write("entry_address\tname\tbody_bytes\n");
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        int n = 0;
        while (it.hasNext()) {
            Function f = it.next();
            w.write(f.getEntryPoint().toString()
                + "\t" + f.getName()
                + "\t" + f.getBody().getNumAddresses()
                + "\n");
            n++;
        }
        w.close();
        println("ovr-export: wrote " + n + " functions to " + out);
    }
}
