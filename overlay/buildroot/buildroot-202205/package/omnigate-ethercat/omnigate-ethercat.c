/*
 * Bounded EtherCAT diagnostics for OmniGate.
 *
 * SOEM and this integration are distributed under GPL-3.0-or-later.
 * Product builds may instead use SOEM under its commercial license.
 */

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "soem/soem.h"

#define IO_MAP_SIZE 65536
#define SDO_MAX_SIZE 4096

typedef struct
{
   ecx_contextt context;
   uint8 io_map[IO_MAP_SIZE];
} master_t;

static void usage(const char *program)
{
   fprintf(stderr,
           "Usage:\n"
           "  %s IFACE scan\n"
           "  %s IFACE sdo-read SLAVE INDEX SUBINDEX [MAX-BYTES]\n"
           "  %s IFACE sdo-write SLAVE INDEX SUBINDEX HEX-BYTES\n"
           "  %s IFACE cycle [COUNT] [PERIOD-US]\n",
           program, program, program, program);
}

static long parse_number(const char *text, long minimum, long maximum,
                         const char *name)
{
   char *end = NULL;
   long value;

   errno = 0;
   value = strtol(text, &end, 0);
   if (errno || !end || *end || value < minimum || value > maximum)
   {
      fprintf(stderr, "Invalid %s: %s\n", name, text);
      exit(2);
   }
   return value;
}

static void json_string(const char *value)
{
   const unsigned char *cursor = (const unsigned char *)value;

   putchar('"');
   while (*cursor)
   {
      switch (*cursor)
      {
         case '"':  fputs("\\\"", stdout); break;
         case '\\': fputs("\\\\", stdout); break;
         case '\b': fputs("\\b", stdout); break;
         case '\f': fputs("\\f", stdout); break;
         case '\n': fputs("\\n", stdout); break;
         case '\r': fputs("\\r", stdout); break;
         case '\t': fputs("\\t", stdout); break;
         default:
            if (*cursor < 0x20)
               printf("\\u%04x", *cursor);
            else
               putchar(*cursor);
      }
      ++cursor;
   }
   putchar('"');
}

static const char *state_name(uint16 state)
{
   switch (state & 0x0f)
   {
      case EC_STATE_INIT: return "INIT";
      case EC_STATE_PRE_OP: return "PRE-OP";
      case EC_STATE_BOOT: return "BOOT";
      case EC_STATE_SAFE_OP: return "SAFE-OP";
      case EC_STATE_OPERATIONAL: return "OP";
      default: return "UNKNOWN";
   }
}

static int master_open(master_t *master, const char *interface)
{
   memset(master, 0, sizeof(*master));
   if (!ecx_init(&master->context, interface))
   {
      fprintf(stderr, "Cannot open raw EtherCAT socket on %s\n", interface);
      return 1;
   }
   if (ecx_config_init(&master->context) <= 0)
   {
      fprintf(stderr, "No EtherCAT slaves found on %s\n", interface);
      ecx_close(&master->context);
      return 3;
   }
   return 0;
}

static void master_close(master_t *master)
{
   ecx_close(&master->context);
}

static int command_scan(master_t *master, const char *interface)
{
   ecx_contextt *context = &master->context;
   int slave;

   ecx_readstate(context);
   printf("{\"ok\":true,\"interface\":");
   json_string(interface);
   printf(",\"count\":%d,\"slaves\":[", context->slavecount);
   for (slave = 1; slave <= context->slavecount; ++slave)
   {
      ec_slavet *item = &context->slavelist[slave];
      if (slave > 1)
         putchar(',');
      printf("{\"position\":%d,\"name\":", slave);
      json_string(item->name);
      printf(",\"state\":\"%s\",\"state_code\":%u,"
             "\"al_status\":%u,\"al_status_text\":",
             state_name(item->state), item->state, item->ALstatuscode);
      json_string(ec_ALstatuscode2string(item->ALstatuscode));
      printf(",\"config_address\":%u,\"alias_address\":%u,"
             "\"vendor_id\":%u,\"product_code\":%u,\"revision\":%u,"
             "\"serial\":%u,\"input_bits\":%u,\"output_bits\":%u,"
             "\"coe\":%s,\"dc\":%s}",
             item->configadr, item->aliasadr, item->eep_man, item->eep_id,
             item->eep_rev, item->eep_ser, item->Ibits, item->Obits,
             item->CoEdetails ? "true" : "false",
             item->hasdc ? "true" : "false");
   }
   puts("]}");
   return 0;
}

static int parse_hex(const char *text, uint8 *buffer, int capacity)
{
   int high = -1;
   int length = 0;

   while (*text)
   {
      int value;
      if (isspace((unsigned char)*text) || *text == ':' || *text == '-')
      {
         ++text;
         continue;
      }
      if (*text == '0' && (text[1] == 'x' || text[1] == 'X') && high < 0)
      {
         text += 2;
         continue;
      }
      if (*text >= '0' && *text <= '9')
         value = *text - '0';
      else if (*text >= 'a' && *text <= 'f')
         value = *text - 'a' + 10;
      else if (*text >= 'A' && *text <= 'F')
         value = *text - 'A' + 10;
      else
         return -1;
      if (high < 0)
         high = value;
      else
      {
         if (length >= capacity)
            return -1;
         buffer[length++] = (uint8)((high << 4) | value);
         high = -1;
      }
      ++text;
   }
   return high < 0 ? length : -1;
}

static int command_sdo_read(master_t *master, int slave, uint16 index,
                            uint8 subindex, int maximum)
{
   uint8 data[SDO_MAX_SIZE];
   int size = maximum;
   int workcounter;
   int offset;

   memset(data, 0, sizeof(data));
   workcounter = ecx_SDOread(&master->context, (uint16)slave, index, subindex,
                            FALSE, &size, data, EC_TIMEOUTRXM);
   if (workcounter <= 0)
   {
      fprintf(stderr, "CoE SDO upload failed (slave %d, 0x%04x:%02x)\n",
              slave, index, subindex);
      return 4;
   }
   printf("{\"ok\":true,\"slave\":%d,\"index\":%u,\"subindex\":%u,"
          "\"length\":%d,\"hex\":\"",
          slave, index, subindex, size);
   for (offset = 0; offset < size; ++offset)
      printf("%s%02x", offset ? " " : "", data[offset]);
   puts("\"}");
   return 0;
}

static int command_sdo_write(master_t *master, int slave, uint16 index,
                             uint8 subindex, const char *hex)
{
   uint8 data[SDO_MAX_SIZE];
   int size = parse_hex(hex, data, sizeof(data));
   int workcounter;

   if (size <= 0)
   {
      fputs("HEX-BYTES must contain 1..4096 complete bytes\n", stderr);
      return 2;
   }
   workcounter = ecx_SDOwrite(&master->context, (uint16)slave, index, subindex,
                             FALSE, size, data, EC_TIMEOUTRXM);
   if (workcounter <= 0)
   {
      fprintf(stderr, "CoE SDO download failed (slave %d, 0x%04x:%02x)\n",
              slave, index, subindex);
      return 4;
   }
   printf("{\"ok\":true,\"slave\":%d,\"index\":%u,\"subindex\":%u,"
          "\"written\":%d}\n", slave, index, subindex, size);
   return 0;
}

static int command_cycle(master_t *master, int count, int period_us)
{
   ecx_contextt *context = &master->context;
   ec_groupt *group = &context->grouplist[0];
   int expected;
   int failures = 0;
   int minimum = INT_MAX;
   int maximum = INT_MIN;
   int total = 0;
   int cycle;

   if (ecx_config_map_group(context, master->io_map, 0) <= 0)
   {
      fputs("EtherCAT process-data mapping failed\n", stderr);
      return 4;
   }
   ecx_configdc(context);
   ecx_statecheck(context, 0, EC_STATE_SAFE_OP, EC_TIMEOUTSTATE * 2);
   ecx_send_processdata(context);
   ecx_receive_processdata(context, EC_TIMEOUTRET);
   context->slavelist[0].state = EC_STATE_OPERATIONAL;
   ecx_writestate(context, 0);

   for (cycle = 0; cycle < 20; ++cycle)
   {
      ecx_send_processdata(context);
      ecx_receive_processdata(context, EC_TIMEOUTRET);
      ecx_statecheck(context, 0, EC_STATE_OPERATIONAL, EC_TIMEOUTSTATE / 20);
      if (context->slavelist[0].state == EC_STATE_OPERATIONAL)
         break;
   }
   if (context->slavelist[0].state != EC_STATE_OPERATIONAL)
   {
      fputs("Not all EtherCAT slaves reached OP state\n", stderr);
      return 5;
   }

   expected = group->outputsWKC * 2 + group->inputsWKC;
   for (cycle = 0; cycle < count; ++cycle)
   {
      int workcounter;
      ecx_send_processdata(context);
      workcounter = ecx_receive_processdata(context, EC_TIMEOUTRET);
      if (workcounter < minimum) minimum = workcounter;
      if (workcounter > maximum) maximum = workcounter;
      total += workcounter;
      if (workcounter != expected) ++failures;
      osal_usleep((uint32)period_us);
   }

   context->slavelist[0].state = EC_STATE_SAFE_OP;
   ecx_writestate(context, 0);
   printf("{\"ok\":%s,\"cycles\":%d,\"period_us\":%d,\"expected_wkc\":%d,"
          "\"min_wkc\":%d,\"max_wkc\":%d,\"average_wkc\":%.3f,"
          "\"wkc_failures\":%d,\"input_bytes\":%u,\"output_bytes\":%u}\n",
          failures ? "false" : "true", count, period_us, expected,
          minimum, maximum, (double)total / count, failures,
          group->Ibytes, group->Obytes);
   return failures ? 6 : 0;
}

int main(int argc, char **argv)
{
   master_t master;
   const char *interface;
   const char *action;
   int result;

   if (argc < 3)
   {
      usage(argv[0]);
      return 2;
   }
   interface = argv[1];
   action = argv[2];
   result = master_open(&master, interface);
   if (result)
      return result;

   if (!strcmp(action, "scan") && argc == 3)
      result = command_scan(&master, interface);
   else if (!strcmp(action, "sdo-read") && (argc == 6 || argc == 7))
      result = command_sdo_read(
         &master,
         (int)parse_number(argv[3], 1, master.context.slavecount, "slave"),
         (uint16)parse_number(argv[4], 0, 0xffff, "index"),
         (uint8)parse_number(argv[5], 0, 0xff, "subindex"),
         argc == 7 ? (int)parse_number(argv[6], 1, SDO_MAX_SIZE, "max bytes") : SDO_MAX_SIZE);
   else if (!strcmp(action, "sdo-write") && argc == 7)
      result = command_sdo_write(
         &master,
         (int)parse_number(argv[3], 1, master.context.slavecount, "slave"),
         (uint16)parse_number(argv[4], 0, 0xffff, "index"),
         (uint8)parse_number(argv[5], 0, 0xff, "subindex"), argv[6]);
   else if (!strcmp(action, "cycle") && argc >= 3 && argc <= 5)
      result = command_cycle(
         &master,
         argc >= 4 ? (int)parse_number(argv[3], 1, 10000, "count") : 100,
         argc >= 5 ? (int)parse_number(argv[4], 100, 1000000, "period") : 1000);
   else
   {
      usage(argv[0]);
      result = 2;
   }

   master_close(&master);
   return result;
}
