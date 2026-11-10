#!/usr/bin/python

"""
    STELA script for exalta 3 orbit decay

"""
import shutil
import tempfile
import platform
import datetime
import traceback

import subprocess as sp
import xml.dom.minidom as xml

from sys import exit
from pathlib import Path
import xml.etree.ElementTree as ET


# INTERNAL VARIABLES. Do not change unless you know what you are doing
__temporaryfile = Path(tempfile.NamedTemporaryFile().name + "stela_tmp_sim.xml")
__workingfile = Path(tempfile.NamedTemporaryFile().name + "stela_work_sim.xml")

# when this flag is enabled, debug mode is activated
DEBUG_MODE = False

# STELA_ROOT set during install. 
STELA_ROOT = Path(r'C:\Stela')


class StelaError(Exception):
    """Exception class specific to running Stela.

    Args:
        status_code (int): Return code for exit
        message (str): Message of the exception
    """

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class XMLFile:
    """Class for XML file manipulation to avoid parsing and rewriting of files on disk over and over.

    Any XML data is accessible using its key as an attribute of the object. This means that no public additional
    attributes can be set, only keys of the XML file will be accepted.

    Args:
        filepath (Path): Path to XML file
    """

    def __init__(self, filepath):
        # Read the document content
        try:
            self._doc = xml.parse(str(filepath))
        except Exception:
            raise StelaError(170, f"The file <{filepath}> isn't a valid XML file.")

        self._path = filepath

    def _get_node(self, key):
        """Retrieve the XML node associated with the key. To get elements from the 'finalState' node, add 'final' in
        front of the key.

        Args:
            key (str): Key for which we want the associated node

        Returns:
            xml.Node: The Node instance associated to the first element found
        """
        try:

            # Case of final value
            key = key.split('final')[1]
            try:
                node_list = self._doc.getElementsByTagName("finalState")[0].getElementsByTagName(key)
            except IndexError:
                raise StelaError(190, f"The element finalState couldn't be foudn in the XML file.")

        except IndexError:
            # Regular case
            node_list = self._doc.getElementsByTagName(key)

        try:
            node = node_list[0]
        except IndexError:
            raise StelaError(40, "Key <" + key + "> not found")

        return node

    def __getattr__(self, item):
        # Retrieve XML node
        node = self._get_node(item)

        try:
            val = float(node.firstChild.nodeValue)
        except ValueError:
            print(f"{item} is not a float. Converting to String")
            val = str(node.firstChild.nodeValue)
        except:
            raise StelaError(180, f"Error on getting {item}")

        return val

    def __setattr__(self, key, value):
        # No public attributes can be set
        if key.startswith('_') or key in dir(self):
            super().__setattr__(key, value)
        else:
            # Retrieve XML node
            node = self._get_node(key)

            # Write the data
            node.firstChild.nodeValue = str(value)

    def write_to_disk(self):
        """Write the file to disk. To use after all modifications have been performed to avoid read/write issues
        (mainly script slowdowns)"""
        with open(self._path, "w") as xml_file:
            self._doc.writexml(xml_file, encoding="ISO-8859-1")


# ######################################## METHODS ########################################

def debug(mess):
    """Print a debug message if DEBUG_MODE is true

    Args:
        mess (str): Debug message
    """
    if DEBUG_MODE:
        print(f"DEBUG# {mess}")


def copy(src, dest):
    """Copy source file to its destination

    Args:
        src (Path): Path to the source
        dest (Path): Path to the destination

    Raises:
        StelaError: The source file cannot be found or the destination file is the same as the source.

    """
    debug(f"copy {src} to {dest}")
    try:
        shutil.copy(src, dest)

    except FileNotFoundError:
        raise StelaError(10, f"File <{src}> not found")

    except shutil.SameFileError:
        raise StelaError(20, f"Copy destination is the same as the source (<{src}>)")


def move_extrapolation_file(src, dest):
    """Move the XML and TXT extrapolation files.

    Args:
        src (Path): Path to the source XML file
        dest (Path): Path to the destination XML file

    Raises:
        StelaError: The source files cannot be found or the provided paths don't end with .xml
    """
    if src.suffix != ".xml":
        raise StelaError(130, f"The provided source file <{src}> is not an XML file")

    if dest.suffix != ".xml":
        raise StelaError(140, f"The provided destination file <{dest}> is not an XML file")

    # XML file move
    try:
        shutil.move(src, dest)
    except FileNotFoundError:
        raise StelaError(150, f"The XML file <{src}> doesn't exist")

    # TXT file move
    src2 = src.with_suffix('.txt')
    try:
        shutil.move(src2, dest.with_suffix('.txt'))
    except FileNotFoundError:
        raise StelaError(160, f"The TXT file <{src2}> doesn't exist")


def remove_file(filepath, missing_ok=False):
    """Remove the specified file

    Args:
        filepath (Path): Path to the file to remove
        missing_ok (bool): If true, an error when attempting to remove the file will not trigger any exception

    Raises:
        StelaError: The specified file doesn't exist.
    """
    try:
        filepath.unlink()
    except FileNotFoundError:
        if not missing_ok:
            raise StelaError(30, f"File <{filepath}> doesn't exist")


def end(exception=None):
    """Function that handles the end of the program.

    Args:
        exception (StelaError):
    """

    if exception is None:
        status_code = 0
        msg = "End prog"
    else:
        status_code = exception.status_code
        msg = str(exception)
    print(f"END PROG (CR={status_code}) # {msg}")
    input('Press enter to finish the program...')
    exit(status_code)


def choseprog():
    """Retrieve the path to the executable file to be executed depending on the platform.

    Returns:
        Path: Path to the executable
    """
    platf = platform.system()
    if platf == 'Linux':
        cmd = STELA_ROOT / "bin" / "stela-batch.sh"
    elif platf == 'Windows':
        cmd = STELA_ROOT / "bin" / "stela-batch.bat"
    else:
        raise StelaError(100, "unknown OS")

    debug(f"PROG : {cmd}")
    
    return cmd


def extrapolate():
    """Launch an extrapolation with workingfile"""
    prog = choseprog() # determines which executable to use based on os
    
    args = [str(prog), "-i", str(__workingfile), "-o", str(__temporaryfile)]

    try:
        sp.run(args, check=True)
    except sp.CalledProcessError as err:
        raise StelaError(err.returncode, "Error when launching extrapolation") from err

    # Test if the output file was generated after extrapolation
    if not __temporaryfile.is_file():
        raise StelaError(110, "Error when writing output file during launching extrapolation")
    
    # Overwrite the working files with the temporary ones
    move_extrapolation_file(__temporaryfile, __workingfile)


def logfile(filename, *mess):
    """Send message in a logfile, they are automatically separated by ';'

    Args:
        filename (Path): Path to the log file
        mess: Elements to log
    """
    with open(filename, 'a') as f:
        msg = ';'.join(map(str, mess))
        debug(f"IN {filename} > {msg}")
        msg += '\n'
        f.write(msg)


def run_sim( __defaultlogfile):

    # uses __workingfile
    try:
       

        print("=========== START ===========")
        
       
        extrapolate()

        # Load working file
        f = XMLFile(__workingfile)


        logfile(__defaultlogfile, f.apogeeAltitude, f.perigeeAltitude, f.inclination, f.rAAN, f.argOfPerigee, f.meanAnomaly,
                f.finalapogeeAltitude, f.finalperigeeAltitude, f.finalinclination, f.finalrAAN, f.finalargOfPerigee, f.finalmeanAnomaly, f.finaldate)
       

        # Update XML file
        f.write_to_disk()


    except StelaError as err:
        end(err)

    except Exception:
        print(traceback.format_exc())
        end(StelaError(999, "Unhandled exception"))

    else:
        print("=========== END ===========")
        print(f"Results are available in file : {__defaultlogfile}")

        return f
    
    

# ######################################## MAIN ########################################
def main():


    __currentfile = Path("sim1.xml")


    __defaultlogfile = Path("log_file.csv")
    remove_file(__defaultlogfile, missing_ok=True)

    logfile(__defaultlogfile, "# STELA Sim")
    logfile(__defaultlogfile, "# By <Your name>")
    logfile(__defaultlogfile, f"# {datetime.datetime.now().ctime()}")
    logfile(__defaultlogfile, "apogeeAltitude(BULL_IN)","perigeeAltitude(BULL_IN)",  "inclination(BULL_IN)",
        "rAAN(BULL_IN)", "argOfPerigee(BULL_IN)", "meanAnomaly(BULL_IN)",
        "apogeeAltitude(BULL_OUT)", "perigeeAltitude(BULL_OUT)", "inclination(BULL_OUT)", "rAAN(BULL_OUT)",
        "argOfPerigee(BULL_OUT)", "meanAnomaly(BULL_OUT)")

    drag_values = ('0.016384742', '0.085131969', '0.0507583555')

    print("ExAlta-3 Orbit Decay Assessment")

    current_stage = int(input("Input current stage of mission (1, 2, 3): "))


    # get dates
    stage_end_dates = {}
    for i in range(current_stage, len(drag_values)+1):
        end_date = input(f"Enter end date for Stage {i} (yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS): \n").strip()

        if len(end_date) == 10:
            end_date += "T00:00:00.000"
        stage_end_dates[i] = end_date

    

    tree = ET.parse(__currentfile)
    root = tree.getroot()
    type0_pos_vel = root.find('.//EphemerisManager/initState/bulletin/Type0PosVel')


   # input inital parameters
    for val in type0_pos_vel:
        val.text = str(input(f"Enter initial {val.tag}: "))
    
    
    # tree.find('.//initState/bulletin/date').text = str(init_date)

    # write tree object to xml file
    tree.write(__currentfile, encoding='ISO-8859-1', xml_declaration=True)
    print(f"Successfully updated initial state and saved to: {__currentfile}")



    

    init_date = datetime.datetime.now().isoformat()
    # ===================== loop ==========================================
    for i in range(current_stage, len(drag_values)+1):

        print(f"\nProcessing Stage {i}...")
        

        # tree mhmmm
        tree = ET.parse(__currentfile)
        root = tree.getroot()

        # update drag area
        drag_area_elem = root.find(".//SpaceObject/dragArea")
        if drag_area_elem is None:
            raise StelaError(200, "dragArea tag not found in XML (check the path)")
        
        drag_area_elem.text = str(drag_values[i-1])


        
        if i > current_stage:
            
            init_state_elem = root.find(".//EphemerisManager/initState")
            bulletin = init_state_elem.find("bulletin")
            pos = bulletin.find("Type0PosVel")
            
            try:
                bulletin.find("date").text = str(f.finaldate)

                pos.find("apogeeAltitude").text = str(f.finalapogeeAltitude)
                pos.find("perigeeAltitude").text = str(f.finalperigeeAltitude)
                pos.find("inclination").text = str(f.finalinclination)
                pos.find("rAAN").text = str(f.finalrAAN)
                pos.find("argOfPerigee").text = str(f.finalargOfPerigee)
                pos.find("meanAnomaly").text = str(f.finalmeanAnomaly)

                tree.write(__currentfile, encoding='ISO-8859-1', xml_declaration=True)

            except AttributeError as e:
                print("Tag not found: ", e)
            
            init_date = bulletin.find("date").text

        

        start_dt = datetime.datetime.fromisoformat(init_date)
        end_dt = datetime.datetime.fromisoformat(stage_end_dates[i])
        
        sim_duration = (end_dt - start_dt).days / 365.25
        print(start_dt, end_dt, sim_duration)

        print(f"Current XML file: {__currentfile}")

        root.find(".//simulationDuration").text = str(sim_duration)
        tree.find('.//initState/bulletin/date').text = str(init_date)
       
        #write changes to current file
        tree.write(__currentfile, encoding="ISO-8859-1", xml_declaration=True)

        

        # run the simulation
        copy(__currentfile, __workingfile)
        print(f"Running simulation for Stage {i} using {__currentfile}...")
        f = run_sim( __defaultlogfile)

        final_dt = datetime.datetime.fromisoformat(f.finaldate)
        if final_dt < end_dt - datetime.timedelta(days=1):
            print(f"Simulation ended early on {f.finaldate} (re-entry/decay). Stopping.")
            break


        # make next XML file
        stage_xml_filename = Path(f"sim_stage_{i}.xml")
        tree.write(stage_xml_filename, encoding="ISO-8859-1", xml_declaration=True)

        __currentfile = stage_xml_filename

    print("\nAll simulation stages completed successfully.")

    print(f"Final date: {f.finaldate}")
    end()


if __name__ == '__main__':
    main()
