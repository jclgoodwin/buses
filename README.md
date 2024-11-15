# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| accounts/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| accounts/admin.py                                               |       41 |        0 |    100% |           |
| accounts/forms.py                                               |       50 |        0 |    100% |           |
| accounts/models.py                                              |       25 |        0 |    100% |           |
| accounts/tests.py                                               |       99 |        0 |    100% |           |
| accounts/urls.py                                                |        4 |        0 |    100% |           |
| accounts/views.py                                               |       61 |        1 |     98% |       108 |
| api/\_\_init\_\_.py                                             |        0 |        0 |    100% |           |
| api/api.py                                                      |       11 |        0 |    100% |           |
| api/filters.py                                                  |       53 |        0 |    100% |           |
| api/serializers.py                                              |      108 |        0 |    100% |           |
| api/tests.py                                                    |        7 |        0 |    100% |           |
| api/views.py                                                    |       73 |        0 |    100% |           |
| buses/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| buses/context\_processors.py                                    |        5 |        0 |    100% |           |
| buses/jinja2.py                                                 |       36 |        2 |     94% |    40, 61 |
| buses/settings.py                                               |      112 |       21 |     81% |97-105, 125, 208, 227-235, 252-268, 319 |
| buses/tests.py                                                  |        5 |        0 |    100% |           |
| buses/urls.py                                                   |        6 |        0 |    100% |           |
| buses/utils.py                                                  |       24 |        1 |     96% |        27 |
| busstops/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| busstops/admin.py                                               |      323 |       16 |     95% |103-109, 184, 243-251, 333-334, 380, 455, 459, 508, 540, 584, 588, 612, 616 |
| busstops/forms.py                                               |       46 |        0 |    100% |           |
| busstops/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| busstops/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| busstops/management/commands/import\_noc.py                     |      130 |        3 |     98% |155, 184, 246 |
| busstops/management/commands/naptan\_new.py                     |      151 |        5 |     97% |47, 100, 152, 212, 257 |
| busstops/management/commands/nptg\_new.py                       |       94 |        7 |     93% |148, 158, 163, 169-170, 172-173 |
| busstops/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| busstops/management/tests/test\_import\_ie.py                   |       63 |        0 |    100% |           |
| busstops/management/tests/test\_import\_naptan.py               |       67 |        0 |    100% |           |
| busstops/management/tests/test\_import\_nptg.py                 |       31 |        0 |    100% |           |
| busstops/management/tests/test\_import\_operators.py            |       64 |        0 |    100% |           |
| busstops/middleware.py                                          |       20 |        0 |    100% |           |
| busstops/models.py                                              |      618 |       24 |     96% |241, 287, 389, 426, 476, 502, 592, 630, 722, 786, 824-828, 833, 844, 863-864, 958-962, 1020, 1062, 1077, 1113 |
| busstops/templatetags/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| busstops/templatetags/date\_range.py                            |       25 |        3 |     88% | 9, 22, 28 |
| busstops/templatetags/urlise.py                                 |       20 |        0 |    100% |           |
| busstops/test\_admin.py                                         |       54 |        0 |    100% |           |
| busstops/test\_middleware.py                                    |       10 |        0 |    100% |           |
| busstops/test\_models.py                                        |      143 |        0 |    100% |           |
| busstops/test\_views.py                                         |      277 |        0 |    100% |           |
| busstops/urls.py                                                |       20 |        2 |     90% |   123-125 |
| busstops/utils.py                                               |        3 |        0 |    100% |           |
| busstops/views.py                                               |      623 |       46 |     93% |116, 136-140, 486, 512, 562, 726, 757, 821-824, 826, 940-945, 958, 1035, 1191, 1241-1242, 1247-1248, 1256-1265, 1282-1286, 1367, 1394-1395, 1399-1402, 1552, 1564-1565, 1570, 1582-1583 |
| bustimes/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| bustimes/admin.py                                               |       97 |       12 |     88% |54, 60, 63-64, 67-68, 114-118, 141, 149, 162, 172 |
| bustimes/download\_utils.py                                     |       40 |        0 |    100% |           |
| bustimes/fields.py                                              |       31 |        1 |     97% |        12 |
| bustimes/formatting.py                                          |       19 |        0 |    100% |           |
| bustimes/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| bustimes/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| bustimes/management/commands/import\_atco\_cif.py               |      235 |       25 |     89% |28-35, 40, 43-44, 66, 193, 195, 198, 200, 208, 214, 278, 311-316, 356-357, 424 |
| bustimes/management/commands/import\_bod\_timetables.py         |      274 |       28 |     90% |48, 99, 103, 107-115, 120, 125-126, 146, 175, 185, 196, 264, 274-278, 294-295, 316, 332-333, 349 |
| bustimes/management/commands/import\_gtfs.py                    |      237 |       24 |     90% |46, 77, 81, 131-132, 148, 209, 211, 271-272, 274-275, 311-312, 318-319, 323-326, 334-336, 384, 406 |
| bustimes/management/commands/import\_gtfs\_ember.py             |       89 |        0 |    100% |           |
| bustimes/management/commands/import\_gtfs\_flixbus.py           |      120 |        3 |     98% |     92-94 |
| bustimes/management/commands/import\_ni.py                      |       31 |        0 |    100% |           |
| bustimes/management/commands/import\_passenger.py               |      118 |       35 |     70% |51-54, 56-58, 102, 112-118, 146-179 |
| bustimes/management/commands/import\_tnds.py                    |       61 |        5 |     92% |46-48, 63-71 |
| bustimes/management/commands/import\_transxchange.py            |      771 |       74 |     90% |79, 91, 137-138, 363, 366-380, 407, 576-577, 614-615, 617-618, 641-642, 652, 660-661, 719, 730, 766, 792, 796-798, 852-856, 917, 921, 923, 939-944, 981-982, 993, 1015, 1017-1020, 1025, 1039, 1045, 1072, 1111, 1142-1143, 1171, 1175-1176, 1187, 1192, 1204, 1229, 1278-1279, 1308-1309, 1314, 1325 |
| bustimes/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_atco\_cif.py            |       70 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_bod.py                  |      226 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs.py                 |      106 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_gtfs\_ember\_flixbus.py |       75 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_ni.py                   |       21 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_passenger.py            |       23 |        0 |    100% |           |
| bustimes/management/tests/test\_import\_transxchange.py         |      726 |        0 |    100% |           |
| bustimes/management/tests/test\_tnds.py                         |       22 |        0 |    100% |           |
| bustimes/models.py                                              |      318 |        6 |     98% |92, 339, 342, 371, 408, 442 |
| bustimes/tests.py                                               |      130 |        0 |    100% |           |
| bustimes/timetables.py                                          |      638 |       48 |     92% |62, 102-115, 144, 241-242, 259, 327-330, 342, 355-360, 406, 413, 481, 484, 500-503, 530, 639-654, 740-741, 812, 958-960 |
| bustimes/urls.py                                                |        3 |        0 |    100% |           |
| bustimes/utils.py                                               |      188 |       12 |     94% |204, 230-232, 252-253, 276, 321, 338-339, 351, 387 |
| bustimes/views.py                                               |      365 |       66 |     82% |154-168, 177-179, 187-196, 198-206, 213, 235, 325, 334, 371, 377, 457, 507, 541, 545-547, 555, 570-577, 607-618, 627-633 |
| departures/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| departures/avl.py                                               |       12 |        1 |     92% |        14 |
| departures/gtfsr.py                                             |       91 |        2 |     98% |   91, 111 |
| departures/live.py                                              |      133 |       14 |     89% |44, 59, 61, 63, 80-85, 143, 154, 166, 180 |
| departures/sources.py                                           |      218 |       34 |     84% |30, 54, 59, 63, 96, 112, 122, 125-127, 137-144, 149-150, 164-165, 173-174, 179, 243, 310, 385, 389-390, 396-397, 400, 408 |
| departures/test\_gtfsr\_trip\_updates.py                        |       45 |        0 |    100% |           |
| departures/test\_gtfsr\_vehicle\_positions.py                   |       33 |        0 |    100% |           |
| departures/test\_live.py                                        |      111 |        0 |    100% |           |
| disruptions/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| disruptions/admin.py                                            |       26 |        1 |     96% |        44 |
| disruptions/models.py                                           |       70 |        5 |     93% |41, 70, 94, 102, 112 |
| disruptions/siri\_sx.py                                         |      122 |       14 |     89% |50, 77, 89-92, 103-104, 135, 145-149 |
| disruptions/test\_siri\_sx.py                                   |       48 |        0 |    100% |           |
| disruptions/test\_tfl\_disruptions.py                           |       34 |        0 |    100% |           |
| disruptions/tests.py                                            |       16 |        0 |    100% |           |
| disruptions/tfl\_disruptions.py                                 |       85 |        2 |     98% |   63, 104 |
| disruptions/urls.py                                             |        3 |        0 |    100% |           |
| disruptions/views.py                                            |        9 |        0 |    100% |           |
| fares/\_\_init\_\_.py                                           |        0 |        0 |    100% |           |
| fares/admin.py                                                  |       37 |        2 |     95% |    26, 29 |
| fares/forms.py                                                  |       26 |        3 |     88% | 17, 40-41 |
| fares/management/commands/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| fares/management/commands/import\_netex\_fares.py               |      353 |       59 |     83% |28, 69-70, 121, 128-130, 223-224, 323, 367-368, 449, 528-535, 555, 564-565, 583-588, 595-632, 652-653, 663-664, 670-679 |
| fares/management/commands/mytrip\_ticketing.py                  |       38 |        3 |     92% | 15, 44-45 |
| fares/models.py                                                 |      176 |        8 |     95% |60, 142, 217, 222, 245-246, 250-251 |
| fares/mytrip.py                                                 |       53 |        4 |     92% |35, 49-50, 73 |
| fares/test\_mytrip.py                                           |       40 |        0 |    100% |           |
| fares/tests.py                                                  |       79 |        0 |    100% |           |
| fares/urls.py                                                   |        3 |        0 |    100% |           |
| fares/views.py                                                  |       44 |        0 |    100% |           |
| manage.py                                                       |        6 |        0 |    100% |           |
| transxchange/\_\_init\_\_.py                                    |        0 |        0 |    100% |           |
| transxchange/test\_txc.py                                       |       23 |        0 |    100% |           |
| transxchange/txc.py                                             |      464 |       16 |     97% |42, 113, 160, 218, 246, 292-299, 396, 408, 470, 503-504, 662, 693 |
| vehicles/\_\_init\_\_.py                                        |        0 |        0 |    100% |           |
| vehicles/admin.py                                               |      250 |       34 |     86% |32, 60, 87, 89, 182-183, 192, 205-206, 222, 251, 254, 277, 283, 285, 287, 290, 319, 337, 343, 381-396, 409, 422, 439, 488-490 |
| vehicles/apps.py                                                |        6 |        0 |    100% |           |
| vehicles/context\_processors.py                                 |       14 |        0 |    100% |           |
| vehicles/fields.py                                              |       15 |        0 |    100% |           |
| vehicles/filters.py                                             |       18 |        0 |    100% |           |
| vehicles/forms.py                                               |       95 |        2 |     98% |  136, 174 |
| vehicles/management/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| vehicles/management/commands/\_\_init\_\_.py                    |        0 |        0 |    100% |           |
| vehicles/management/commands/import\_bod\_avl.py                |      476 |       56 |     88% |50, 128, 144, 153-154, 197-200, 203-206, 258, 274, 293-294, 317-335, 389, 395, 448, 451, 455, 461, 476-477, 524-537, 566, 575-576, 595, 624, 657, 775, 850, 854 |
| vehicles/management/commands/import\_bushub.py                  |       76 |       14 |     82% |22-23, 27-28, 31-32, 43, 46, 62-63, 72, 82, 101, 109 |
| vehicles/management/commands/import\_edinburgh.py               |       72 |        4 |     94% |83, 87-90, 97 |
| vehicles/management/commands/import\_gtfsr\_ember.py            |       86 |        7 |     92% |78-79, 102-104, 120, 141 |
| vehicles/management/commands/import\_gtfsr\_ie.py               |      102 |        6 |     94% |71, 98, 143, 152, 159, 163 |
| vehicles/management/commands/import\_live\_jersey.py            |       33 |        0 |    100% |           |
| vehicles/management/commands/import\_polar.py                   |       78 |       27 |     65% |13-14, 25, 28, 33-39, 45-47, 51, 55-56, 61-62, 65, 75-78, 81, 94, 101 |
| vehicles/management/commands/import\_stagecoach\_avl.py         |       96 |       15 |     84% |105, 116-127, 155, 168, 173-174, 185-191, 213-221 |
| vehicles/management/commands/siri\_vm\_subscribe.py             |       26 |        0 |    100% |           |
| vehicles/management/import\_live\_vehicles.py                   |      283 |       59 |     79% |38, 51-67, 80, 121, 130, 136-138, 162, 177, 181, 190-193, 202, 215, 223, 228, 232-233, 235-236, 241-242, 256-262, 294-295, 336, 339-340, 354-355, 370-371, 375, 398-399, 406-410, 427, 437-439 |
| vehicles/management/tests/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| vehicles/management/tests/test\_bod\_avl.py                     |      311 |        0 |    100% |           |
| vehicles/management/tests/test\_bushub.py                       |       48 |        0 |    100% |           |
| vehicles/management/tests/test\_edinburgh.py                    |       51 |        0 |    100% |           |
| vehicles/management/tests/test\_import\_live\_jersey.py         |       31 |        0 |    100% |           |
| vehicles/management/tests/test\_polar.py                        |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_siri\_post.py                   |       37 |        0 |    100% |           |
| vehicles/management/tests/test\_stagecoach\_avl.py              |       33 |        0 |    100% |           |
| vehicles/management/tests/test\_stats.py                        |       24 |        0 |    100% |           |
| vehicles/models.py                                              |      527 |       33 |     94% |204, 206, 216, 250, 254, 258, 329, 335, 405, 411, 468, 489, 617-618, 631, 656-658, 666-667, 670-671, 676-677, 699, 761, 768-771, 813, 826, 835, 846 |
| vehicles/rtpi.py                                                |       73 |        1 |     99% |        27 |
| vehicles/signals.py                                             |       17 |        1 |     94% |        24 |
| vehicles/tasks.py                                               |      127 |       22 |     83% |63-73, 80, 85, 95, 102-105, 108, 110, 118, 132, 150, 164, 177-178, 232-233, 236 |
| vehicles/test\_models.py                                        |       67 |        0 |    100% |           |
| vehicles/test\_schedule\_adherence.py                           |       73 |        0 |    100% |           |
| vehicles/tests.py                                               |      439 |        0 |    100% |           |
| vehicles/urls.py                                                |        4 |        0 |    100% |           |
| vehicles/utils.py                                               |      126 |        3 |     98% |41-42, 170 |
| vehicles/views.py                                               |      610 |       70 |     89% |341-342, 393, 420, 435-436, 455-456, 484-485, 512-517, 522-523, 554, 572-573, 575, 580, 596-598, 616-637, 717-718, 725, 739, 843, 845, 847, 852, 901-909, 926-932, 949-950, 991, 1040, 1043-1044, 1054, 1070-1075, 1115-1116, 1162, 1217-1256 |
| vosa/\_\_init\_\_.py                                            |        0 |        0 |    100% |           |
| vosa/admin.py                                                   |       36 |        0 |    100% |           |
| vosa/management/commands/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| vosa/management/commands/import\_vosa.py                        |      159 |        1 |     99% |       203 |
| vosa/models.py                                                  |       75 |        0 |    100% |           |
| vosa/tests.py                                                   |       60 |        0 |    100% |           |
| vosa/urls.py                                                    |        3 |        0 |    100% |           |
| vosa/views.py                                                   |       57 |        0 |    100% |           |
|                                                       **TOTAL** | **15681** |  **993** | **94%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/jclgoodwin/bustimes.org/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/jclgoodwin/bustimes.org/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fjclgoodwin%2Fbustimes.org%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/jclgoodwin/bustimes.org/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.