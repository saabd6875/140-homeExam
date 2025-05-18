# 140-homeExam
DATA2410 home exam

candidate number: 140 
course name: Datanettverk og skytjenester

Overview:
An file transfer application that uses DRTP to give UDP a reliable transport. 


to use the DRTP application, follow these instructions:
for the server:
python application.py -s -i <ip> -p <port> -d <discard_sequence_number>

for the client:
python application.py -c -i <ip> -p <port> -f <file_path> -w <window_size>

HOW TO RUN application.py:
- use ubuntu to have access to mininet (i used Oracle VM virtualbox.
- install required tools: mininet, xterm, and ubuntu utilities.
- use a shared folder to upload needed files.
- run mininet: use sudo mn --custom <custom_topo_file> to start mininet with you custom topology file.
- test the application using the interaction between h1 and h2 (seperate nodes).


