# k6 summary

scenario: teacher_courses

- http_req_receiving: min=0.036, med=0.043, max=0.181, p(90)=0.067, p(95)=0.086, p(99)=0.162, avg=0.054
- http_req_duration: med=43.400, max=48.326, p(90)=45.807, p(95)=45.960, p(99)=47.853, avg=39.914, min=18.045
- iterations: count=20.000, rate=4.150
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_blocked: med=0.011, max=0.132, p(90)=0.015, p(95)=0.022, p(99)=0.110, avg=0.017, min=0.003
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.097, p(90)=0.000, p(95)=0.005, p(99)=0.078, avg=0.005
- http_req_sending: p(95)=0.054, p(99)=0.056, avg=0.041, min=0.011, med=0.043, max=0.056, p(90)=0.050
- http_req_duration{expected_response:true}: med=43.400, max=48.326, p(90)=45.807, p(95)=45.960, p(99)=47.853, avg=39.914, min=18.045
- http_req_waiting: p(99)=47.759, avg=39.820, min=17.992, med=43.251, max=48.228, p(90)=45.703, p(95)=45.879
