# k6 summary

scenario: outline

- http_req_blocked: p(95)=0.016, p(99)=0.100, avg=0.013, min=0.001, med=0.011, max=0.125, p(90)=0.014
- http_req_receiving: max=0.656, p(90)=0.308, p(95)=0.350, p(99)=0.543, avg=0.165, min=0.026, med=0.151
- http_req_duration{expected_response:true}: p(90)=17.024, p(95)=18.064, p(99)=24.977, avg=10.992, min=2.722, med=11.132, max=27.821
- http_req_sending: max=0.169, p(90)=0.053, p(95)=0.062, p(99)=0.076, avg=0.039, min=0.007, med=0.039
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- vus: min=5.000, max=5.000
- http_req_connecting: p(95)=0.000, p(99)=0.077, avg=0.002, min=0.000, med=0.000, max=0.093, p(90)=0.000
- http_req_duration: p(95)=18.064, p(99)=24.977, avg=10.992, min=2.722, med=11.132, max=27.821, p(90)=17.024
- http_req_failed: rate=0.000
- iterations: rate=23.551, count=238.000
- http_req_waiting: min=2.650, med=10.878, max=27.772, p(90)=16.827, p(95)=17.829, p(99)=24.819, avg=10.787
