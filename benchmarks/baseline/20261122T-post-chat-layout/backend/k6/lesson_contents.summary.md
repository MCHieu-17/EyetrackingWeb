# k6 summary

scenario: lesson_contents

- iterations: count=237.000, rate=23.341
- http_req_duration: p(95)=19.265, p(99)=21.110, avg=12.819, min=2.917, med=13.064, max=55.478, p(90)=18.479
- http_req_sending: avg=0.040, min=0.005, med=0.040, max=0.191, p(90)=0.052, p(95)=0.057, p(99)=0.077
- http_req_receiving: med=0.087, max=0.373, p(90)=0.196, p(95)=0.229, p(99)=0.297, avg=0.101, min=0.012
- http_req_blocked: med=0.011, max=0.132, p(90)=0.013, p(95)=0.015, p(99)=0.123, avg=0.013, min=0.002
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_connecting: med=0.000, max=0.097, p(90)=0.000, p(95)=0.000, p(99)=0.091, avg=0.002, min=0.000
- http_req_duration{expected_response:true}: p(99)=21.110, avg=12.819, min=2.917, med=13.064, max=55.478, p(90)=18.479, p(95)=19.265
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_waiting: med=12.889, max=55.419, p(90)=18.363, p(95)=19.180, p(99)=21.001, avg=12.678, min=2.872
