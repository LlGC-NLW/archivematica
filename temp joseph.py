#!/usr/bin/python -OO
# This file is part of Archivematica.
#
# Copyright 2010-2012 Artefactual Systems Inc. <http://artefactual.com>
#
# Archivematica is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Archivematica is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.  If not, see <http://www.gnu.org/licenses/>.

# @package Archivematica
# @subpackage transcoder
# @author Joseph Perry <joseph@artefactual.com>
# @version svn: $Id$

import uuid
import sys
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseInterface
import traceback

databaseInterface.printSQL = True


#used to control testing of an individual call to databaseInterface.runSQL() 
def runSQL(sql):
    if True:
        databaseInterface.runSQL(sql)
    if True:
        sys.stdout.flush()
        sys.stderr.flush()


#(table, column Type, column Type Value, column FK):(table, column)
combinedForeignKeys = {
    ("TasksConfigs", "taskType", "0", "taskTypePKReference"):("StandardTasksConfigs", "pk"),
    ("TasksConfigs", "taskType", "1", "taskTypePKReference"):("StandardTasksConfigs", "pk"),
    ("TasksConfigs", "taskType", "3", "taskTypePKReference"):("TasksConfigsAssignMagicLink", "pk"),
    ("TasksConfigs", "taskType", "6", "taskTypePKReference"):("TasksConfigsStartLinkForEachFile", "pk"),
    ("TasksConfigs", "taskType", "7", "taskTypePKReference"):("StandardTasksConfigs", "pk"),
    ("TasksConfigs", "taskType", "8", "taskTypePKReference"):("CommandRelationships", "pk"),
    ("TasksConfigs", "taskType", "9", "taskTypePKReference"):("StandardTasksConfigs", "pk"),   
    ("TasksConfigs", "taskType", "10", "taskTypePKReference"):("StandardTasksConfigs", "pk")
}

def part0():
    try:
        runSQL("""DROP TABLE IF EXISTS TasksConfigsAssignMagicLink;""")
    except:
        print
    runSQL("""CREATE TABLE TasksConfigsAssignMagicLink (
    pk                  INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    execute             INT UNSIGNED,
    Foreign Key (execute) references MicroServiceChainLinks(pk)
) DEFAULT CHARSET=utf8;""")
    
    for row in databaseInterface.queryAllSQL("""SELECT StandardTasksConfigs.pk, execute FROM TasksConfigs JOIN StandardTasksConfigs ON taskTypePKReference = StandardTasksConfigs.pk  WHERE TasksConfigs.taskType = 3;"""):
        runSQL( """INSERT INTO TasksConfigsAssignMagicLink(pk, execute) VALUES ( %s, %s)""" % (row[0].__str__(), row[1]) )
        runSQL( """DELETE FROM StandardTasksConfigs WHERE pk = %s;""" % (row[0].__str__()) )
    
    
        
    #Split creating Jobs for each file
    try:
        runSQL("""DROP TABLE IF EXISTS TasksConfigsStartLinkForEachFile;""")
    except:
        print
    runSQL("""CREATE TABLE TasksConfigsStartLinkForEachFile (
    pk                  INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    filterSubDir        VARCHAR(50),
    execute             INT UNSIGNED,
    Foreign Key (execute) references MicroServiceChains(pk)
) DEFAULT CHARSET=utf8;""")
    
    for row in databaseInterface.queryAllSQL("""SELECT StandardTasksConfigs.pk, StandardTasksConfigs.filterSubDir, execute  FROM TasksConfigs JOIN StandardTasksConfigs ON StandardTasksConfigs.pk = TasksConfigs.taskTypePKReference WHERE TasksConfigs.taskType = 6  GROUP BY StandardTasksConfigs.pk;"""):
        runSQL( """INSERT INTO TasksConfigsStartLinkForEachFile(pk, filterSubDir, execute) VALUES ( %s, '%s', %s)""" % (row[0].__str__(), row[1], row[2]) )
        runSQL( """DELETE FROM StandardTasksConfigs WHERE pk = %s;""" % (row[0].__str__()) )
    
    
    
    runSQL("ALTER TABLE Transfers ADD FOREIGN KEY (magicLink) REFERENCES MicroServiceChainLinks(pk);")
    runSQL("ALTER TABLE SIPs ADD FOREIGN KEY (magicLink) REFERENCES MicroServiceChainLinks(pk);")
    
    

def part1(tables, doPart2=False):
    #find what relationships exist
    sql = """
            select 
            concat(table_name, '.', column_name) as 'foreign key',  
            concat(referenced_table_name, '.', referenced_column_name) as 'references',
            table_name,
            column_name,
            referenced_table_name,
            referenced_column_name,
            CONSTRAINT_NAME
        from
            information_schema.key_column_usage
        where
            referenced_table_name is not null
        AND(
            referenced_table_name = '%s'
        ) GROUP BY concat(table_name, '.', column_name)
        ORDER BY  concat(table_name, '.', column_name);""" % ("' OR \n        referenced_table_name = '".join(tables))
    rowsRelationships = databaseInterface.queryAllSQL(sql)
    
    #Create new pk columns and assign them random UUIDs
    for table in tables:
        sql = "ALTER TABLE %s  ADD newPK VARCHAR(50) AFTER pk;" % (table)
        runSQL(sql)
        sql = "SELECT pk from %s" % (table)
        rows = databaseInterface.queryAllSQL(sql)
        for row in rows:
            UUID = uuid.uuid4().__str__()
            sql = "UPDATE %s SET newPK='%s' WHERE pk = %d;" % (table, UUID, row[0])
            runSQL(sql)
    
    
    #Create new foreign key columns and populate them with the appropriate UUID's
    for row in rowsRelationships:
        #print >>sys.stderr, "\n", row[0], " -> ",  row[1]
        table_name = row[2]
        column_name = row[3]
        referenced_table_name = row[4]
        referenced_column_name = row[5]
        constraint_name = row[6]
        
        runSQL("ALTER TABLE %s ADD %s_new VARCHAR(50) AFTER %s" % (table_name, column_name, column_name) )
            
        sql = "SELECT pk, newPK from %s" % (referenced_table_name)
        rows2 = databaseInterface.queryAllSQL(sql)
        for row2 in rows2:
            pk, newPK = row2
            runSQL("UPDATE %s SET %s='%s' WHERE %s = %d;" % (table_name, column_name+"_new", newPK, column_name, pk ))
           
        runSQL("ALTER TABLE %s DROP FOREIGN KEY %s;" % (table_name, constraint_name) )
        runSQL("ALTER TABLE %s DROP COLUMN %s;" % (table_name, column_name) )
                

    
    if doPart2:
        #create new foreign key columns for implicit
        combinedForeignKeysFKs = {}
        for key, value in combinedForeignKeys.iteritems():
            table, columnType, columnTypeValue, columnFK = key
            combinedForeignKeysFKs[(table, columnType, columnFK)] = None #ensures uniqueness/remove duplicates

        for table, columnType, columnFK in combinedForeignKeysFKs.iterkeys():
            runSQL("ALTER TABLE %s ADD %s_new VARCHAR(50) AFTER %s" % (table, columnFK, columnFK) )

        #check implicit relationships + update new columns
        for key, value in combinedForeignKeys.iteritems():
            referenced_table_name, referenced_column_name = value
            table_name, keyColumn, keyValue, column_name = key
            
            sql = "SELECT pk, newPK from %s" % (referenced_table_name)
            rows2 = databaseInterface.queryAllSQL(sql)
            for row2 in rows2:
                pk, newPK = row2
                runSQL( "UPDATE %s SET %s='%s' WHERE %s = %d AND %s = %s;" % (table_name, column_name+"_new", newPK, column_name, pk, keyColumn, keyValue) )
                    

        #Remove old, rename new columns for implicit relationships
        for table, columnType, columnFK in combinedForeignKeysFKs.iterkeys():
            runSQL("ALTER TABLE %s DROP COLUMN %s;" % (table, columnFK))
            runSQL( "ALTER TABLE %s  CHANGE %s_new %s VARCHAR(50);" % (table, columnFK, columnFK) )
        
    #Set the pk as the new pk, and 
    for table in tables:
        runSQL( "ALTER TABLE %s CHANGE pk pk INT;" % (table) )
        runSQL( "ALTER TABLE %s DROP PRIMARY KEY;" % (table) )
        runSQL( "ALTER TABLE %s ADD PRIMARY KEY (newPK);" % (table) )
        runSQL( "ALTER TABLE %s DROP COLUMN pk;" % (table) )
        runSQL( "ALTER TABLE %s CHANGE newPK pk VARCHAR(50) FIRST;" % (table) )
        runSQL( "ALTER TABLE %s ADD INDEX %s(pk);" % (table, table) )
        

    #rename the fk_new to fk
    #set the fk relationship    
    for row in rowsRelationships:
        #print >>sys.stderr, "\n", row[0], " -> ",  row[1]
        table_name = row[2]
        column_name = row[3]
        referenced_table_name = row[4]
        referenced_column_name = row[5]
        constraint_name = row[6]
        runSQL( "ALTER TABLE %s  CHANGE %s_new %s VARCHAR(50);" % (table_name, column_name, column_name) )
        runSQL( "ALTER TABLE %s ADD FOREIGN KEY (%s) REFERENCES %s(%s)" %(table_name, column_name, referenced_table_name, referenced_column_name) )
           
def part3(tables):    
    for table in tables:
        runSQL( "ALTER TABLE %s ADD replaces VARCHAR(50)" % (table) )
        runSQL( "ALTER TABLE %s ADD lastModified TIMESTAMP" % (table) )
        runSQL( "UPDATE %s SET lastModified=NOW();" % (table) )
        


if __name__ == '__main__':
    tables1 = ['CommandsSupportedBy', 'FileIDs', 'FileIDsByExtension', 'CommandClassifications', 'CommandTypes', 'Commands', 'CommandRelationships', 'DefaultCommandsForClassifications', 'StandardTasksConfigs', 'FileIDGroupMembers', 'FileIDsByPronom', 'Groups', 'TasksConfigsAssignMagicLink', 'TasksConfigsStartLinkForEachFile']
    tables2 = ['MetadataAppliesToTypes', 'MicroServiceChainChoice', 'MicroServiceChainLinks', 'MicroServiceChainLinksExitCodes', 'MicroServiceChains', 'MicroServiceChoiceReplacementDic', 'Sounds', 'SourceDirectories', 'TaskTypes', 'TasksConfigs', 'WatchedDirectories', 'WatchedDirectoriesExpectedTypes']

    part0()
    part1(tables1, doPart2=True)
    part1(tables2)
    part3(tables1 + tables2)
    
#SHOW CREATE TABLE CommandRelationships;
    
    

