# k6 summary

scenario: lesson_contents

- http_req_sending: med=0.040, max=0.132, p(90)=0.050, p(95)=0.054, p(99)=0.080, avg=0.038, min=0.005
- http_req_duration: max=55.954, p(90)=21.167, p(95)=22.366, p(99)=27.683, avg=14.775, min=3.683, med=15.520
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.063, avg=0.001, min=0.000, med=0.000, max=0.087
- vus: min=5.000, max=5.000
- http_req_blocked: avg=0.012, min=0.002, med=0.011, max=0.117, p(90)=0.014, p(95)=0.017, p(99)=0.087
- http_req_receiving: avg=0.085, min=0.011, med=0.057, max=0.775, p(90)=0.176, p(95)=0.259, p(99)=0.478
- iterations: count=235.000, rate=23.072
- http_req_waiting: min=3.618, med=15.311, max=55.882, p(90)=20.989, p(95)=22.289, p(99)=27.558, avg=14.651
- http_req_duration{expected_response:true}: p(90)=21.167, p(95)=22.366, p(99)=27.683, avg=14.775, min=3.683, med=15.520, max=55.954
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
