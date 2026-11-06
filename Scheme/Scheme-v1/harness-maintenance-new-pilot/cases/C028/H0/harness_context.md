The following target source and OSS-Fuzz build wiring are from before the source commit.

### `historical OSS-Fuzz:projects/tidy-html5/build.sh`

~~~~text
#!/bin/bash -eu
#
# Copyright 2018 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

mkdir -p ${WORK}/tidy-html5
cd ${WORK}/tidy-html5

cmake -GNinja ${SRC}/tidy-html5/
ninja

for fuzzer in tidy_config_fuzzer tidy_fuzzer tidy_xml_fuzzer tidy_parse_string_fuzzer tidy_parse_file_fuzzer tidy_general_fuzzer; do
    ${CC} ${CFLAGS} -c -I${SRC}/tidy-html5/include \
        $SRC/${fuzzer}.c -o ${fuzzer}.o
    ${CXX} ${CXXFLAGS} -std=c++11 ${fuzzer}.o \
        -o $OUT/${fuzzer} \
        $LIB_FUZZING_ENGINE libtidy.a
done

cp ${SRC}/*.options ${OUT}/
~~~~

### `historical OSS-Fuzz:projects/tidy-html5/tidy_fuzzer.c`

~~~~c
// Copyright 2018 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "tidy.h"
#include "tidybuffio.h"

void run_tidy_parser(TidyBuffer* data_buffer,
                     TidyBuffer* output_buffer,
                     TidyBuffer* error_buffer) {
    TidyDoc tdoc = tidyCreate();
    if (tidySetErrorBuffer(tdoc, error_buffer) < 0) {
        abort();
    }
    tidyOptSetBool(tdoc, TidyXhtmlOut, yes);
    tidyOptSetBool(tdoc, TidyForceOutput, yes);

    if (tidyParseBuffer(tdoc, data_buffer) >= 0 &&
            tidyCleanAndRepair(tdoc) >= 0 &&
            tidyRunDiagnostics(tdoc) >= 0) {
        tidySaveBuffer(tdoc, output_buffer);
    }
    tidyRelease(tdoc);
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    TidyBuffer data_buffer;
    TidyBuffer output_buffer;
    TidyBuffer error_buffer;
    tidyBufInit(&data_buffer);
    tidyBufInit(&output_buffer);
    tidyBufInit(&error_buffer);

    tidyBufAttach(&data_buffer, (byte*)data, size);
    run_tidy_parser(&data_buffer, &output_buffer, &error_buffer);

    tidyBufFree(&error_buffer);
    tidyBufFree(&output_buffer);
    tidyBufDetach(&data_buffer);
    return 0;
}
~~~~

### `historical OSS-Fuzz:projects/tidy-html5/tidy_general_fuzzer.c`

~~~~c
/*
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include "tidybuffio.h"
#include "tidy.h"

// All boolean options. These will be set randomly
// based on the fuzzer data.
TidyOptionId bool_options[] = {
  TidyJoinClasses, 
  TidyJoinStyles, 
  TidyKeepFileTimes, 
  TidyKeepTabs, 
  TidyLiteralAttribs, 
  TidyLogicalEmphasis, 
  TidyLowerLiterals, 
  TidyMakeBare, 
  TidyFixUri, 
  TidyForceOutput, 
  TidyGDocClean, 
  TidyHideComments,
  TidyMark, 
  TidyXmlTags, 
  TidyMakeClean,
  TidyAnchorAsName, 
  TidyMergeEmphasis, 
  TidyMakeBare, 
  TidyMetaCharset, 
  TidyMuteShow, 
  TidyNCR, 
  TidyNumEntities, 
  TidyOmitOptionalTags, 
  TidyPunctWrap, 
  TidyQuiet,
  TidyQuoteAmpersand,  
  TidyQuoteMarks, 
  TidyQuoteNbsp, 
  TidyReplaceColor, 
  TidyShowFilename, 
  TidyShowInfo, 
  TidyShowMarkup, 
  TidyShowMetaChange, 
  TidyShowWarnings, 
  TidySkipNested, 
  TidyUpperCaseTags, 
  TidyWarnPropAttrs, 
  TidyWord2000, 
  TidyWrapAsp, 
  TidyWrapAttVals, 
  TidyWrapJste, 
  TidyWrapPhp, 
  TidyWrapScriptlets, 
  TidyWrapSection, 
  TidyWriteBack,
};

void set_option(const uint8_t** data, size_t *size, TidyDoc *tdoc, TidyOptionId tboolID) {
  uint8_t decider;
  decider = **data;
  *data += 1; 
  *size -= 1;
  if (decider % 2 == 0) tidyOptSetBool( *tdoc, tboolID, yes );
  else { tidyOptSetBool( *tdoc, tboolID, no ); }
}

int TidyXhtml(const uint8_t* data, size_t size, TidyBuffer* output, TidyBuffer* errbuf) {
  uint8_t decider;

  // We need enough data for picking all of the options. One byte per option.
  if (size < 5+(sizeof(bool_options)/sizeof(bool_options[0]))) {
    return 0;
  }

  TidyDoc tdoc = tidyCreate();

  // Decide output format
  decider = *data;
  data++; size--;
  if (decider % 3 == 0) tidyOptSetBool( tdoc, TidyXhtmlOut, yes );
  else { tidyOptSetBool( tdoc, TidyXhtmlOut, no ); }

  if (decider % 3 == 1) tidyOptSetBool( tdoc, TidyHtmlOut, yes );
  else { tidyOptSetBool( tdoc, TidyHtmlOut, no ); }

  if (decider % 3 == 2) tidyOptSetBool( tdoc, TidyXmlOut, yes );
  else { tidyOptSetBool( tdoc, TidyXmlOut, no ); }

  // Set options 
  for (int i=0; i < sizeof(bool_options)/sizeof(TidyOptionId); i++) {
    set_option(&data, &size, &tdoc, bool_options[i]);
  }

  // Set an error buffer.
  tidySetErrorBuffer(tdoc, errbuf);

  // Parse the data
  decider = *data;
  data++; size--;
  switch (decider % 2) {
    case 0: {
      char filename[256];
      sprintf(filename, "/tmp/libfuzzer.%d", getpid());

      FILE *fp = fopen(filename, "wb");
      if (!fp) {
          return 0;
      }
      fwrite(data, size, 1, fp);
      fclose(fp);

      tidyParseFile(tdoc, filename);
      unlink(filename);
    }
    break;
    case 1: {
      char *inp = malloc(size+1);
      inp[size] = '\0';
      memcpy(inp, data, size);
      tidyParseString(tdoc, inp);
      free(inp);
    }
  }

  // Cleanup
  tidyRelease( tdoc );

  return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  TidyBuffer fuzz_toutput;
  TidyBuffer fuzz_terror;

  tidyBufInit(&fuzz_toutput);
  tidyBufInit(&fuzz_terror);

  TidyXhtml(data, size, &fuzz_toutput, &fuzz_terror);

  tidyBufFree(&fuzz_toutput);
  tidyBufFree(&fuzz_terror);

  return 0;
}
~~~~

### `historical OSS-Fuzz:projects/tidy-html5/tidy_parse_string_fuzzer.c`

~~~~c
/*
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include "tidybuffio.h"
#include "tidy.h"


int TidyXhtml(const char* input, TidyBuffer* output, TidyBuffer* errbuf) {
  TidyDoc tdoc = tidyCreate();
  tidyOptSetBool( tdoc, TidyXhtmlOut, yes );
  tidySetErrorBuffer(tdoc, errbuf);

  tidyParseString(tdoc, input);

  tidyCleanAndRepair(tdoc);
  tidyRunDiagnostics(tdoc);
  tidyOptSetBool(tdoc, TidyForceOutput, yes);
  tidySaveBuffer(tdoc, output);
  tidyRelease( tdoc );
  return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  char *fuzz_inp = malloc(size+1);
  memcpy(fuzz_inp, data, size);
  fuzz_inp[size] = '\0';

  TidyBuffer fuzz_toutput;
  TidyBuffer fuzz_terror;

  tidyBufInit(&fuzz_toutput);
  tidyBufInit(&fuzz_terror);

  TidyXhtml(fuzz_inp, &fuzz_toutput, &fuzz_terror);

  tidyBufFree(&fuzz_toutput);
  tidyBufFree(&fuzz_terror);
  free(fuzz_inp);
  return 0;
}
~~~~

### `historical OSS-Fuzz:projects/tidy-html5/tidy_parse_file_fuzzer.c`

~~~~c
/*
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include "tidybuffio.h"
#include "tidy.h"


int TidyXhtml(const uint8_t* data, size_t size, TidyBuffer* output, TidyBuffer* errbuf) {
  Bool ok;

  TidyDoc tdoc = tidyCreate();

  ok = tidyOptSetBool( tdoc, TidyXhtmlOut, yes );
  if (ok) tidySetErrorBuffer(tdoc, errbuf);
 
  char filename[256];
  sprintf(filename, "/tmp/libfuzzer.%d", getpid());

  FILE *fp = fopen(filename, "wb");
  if (!fp) {
    return 0;
  }
  fwrite(data, size, 1, fp);
  fclose(fp);

  tidyParseFile(tdoc, filename);

  tidyRelease( tdoc );
  unlink(filename);

  return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  TidyBuffer fuzz_toutput;
  TidyBuffer fuzz_terror;

  tidyBufInit(&fuzz_toutput);
  tidyBufInit(&fuzz_terror);

  TidyXhtml(data, size, &fuzz_toutput, &fuzz_terror);

  tidyBufFree(&fuzz_toutput);
  tidyBufFree(&fuzz_terror);
  return 0;
}
~~~~

### `historical OSS-Fuzz:projects/tidy-html5/tidy_xml_fuzzer.c`

~~~~c
/*
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include "tidy.h"
#include "tidybuffio.h"
#include "tidyenum.h"
#include "tidyplatform.h"

void TidyXml(char *fuzz_inp, TidyBuffer *toutput,
             TidyBuffer *terror) {
  TidyDoc tdoc = tidyCreate();
  tidyBufClear(toutput);
  tidyBufClear(terror);
  if (tidyOptSetBool(tdoc, TidyXmlOut, yes)) {
    tidySetCharEncoding(tdoc, "utf8");
    tidySetErrorBuffer(tdoc, terror);
    tidyOptSetInt(tdoc, TidyWrapLen, 0);
    tidyOptSetBool(tdoc, TidyXmlTags, yes);
    tidyOptSetBool(tdoc, TidyQuoteNbsp, no);
    tidyOptSetBool(tdoc, TidyNumEntities, yes);
    tidyOptSetBool(tdoc, TidyQuiet, yes);
    tidyOptSetBool(tdoc, TidyMark, no);
    tidyOptSetBool(tdoc, TidyShowWarnings, no);
    tidyParseString(tdoc, fuzz_inp);
    tidyCleanAndRepair(tdoc);
    tidyRunDiagnostics(tdoc);
    tidySaveBuffer(tdoc, toutput);
  }

  tidyRelease(tdoc);
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  char *fuzz_inp = malloc(size+1);
  memcpy(fuzz_inp, data, size);
  fuzz_inp[size] = '\0';

  TidyBuffer fuzz_toutput;
  TidyBuffer fuzz_terror;

  tidyBufInit(&fuzz_toutput);
  tidyBufInit(&fuzz_terror);

  TidyXml(fuzz_inp, &fuzz_toutput, &fuzz_terror);

  free(fuzz_inp);
  tidyBufFree(&fuzz_toutput);
  tidyBufFree(&fuzz_terror);
  return 0;
}
~~~~

### `historical OSS-Fuzz:projects/tidy-html5/tidy_config_fuzzer.c`

~~~~c
// Copyright 2018 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <stddef.h>
#include <stdint.h>

#include "fuzzer_temp_file.h"
#include "tidy.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    TidyDoc tdoc = tidyCreate();

    // At the time this fuzzer was written, the configuration parser could
    // only be exercised via a file interface.
    char* tmpfile = fuzzer_get_tmpfile(data, size);
    tidyLoadConfig(tdoc, tmpfile);
    fuzzer_release_tmpfile(tmpfile);
    tidyRelease(tdoc);
    return 0;
}
~~~~
