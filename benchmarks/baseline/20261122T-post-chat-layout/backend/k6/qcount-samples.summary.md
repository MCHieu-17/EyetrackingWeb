# k6 summary

scenario: samples

- http_req_duration{expected_response:true}: p(99)=17.714, avg=13.733, min=4.578, med=14.582, max=17.761, p(90)=17.400, p(95)=17.527
- http_req_waiting: max=17.435, p(90)=17.212, p(95)=17.345, p(99)=17.417, avg=13.534, min=4.461, med=14.293
- iterations: count=20.000, rate=4.653
- http_req_duration: max=17.761, p(90)=17.400, p(95)=17.527, p(99)=17.714, avg=13.733, min=4.578, med=14.582
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: max=0.064, p(90)=0.056, p(95)=0.060, p(99)=0.063, avg=0.044, min=0.011, med=0.043
- http_req_receiving: max=0.305, p(90)=0.295, p(95)=0.297, p(99)=0.304, avg=0.155, min=0.036, med=0.135
- http_req_failed: rate=0.000
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.082, p(90)=0.000, p(95)=0.004, p(99)=0.066
- http_req_blocked: avg=0.016, min=0.003, med=0.011, max=0.117, p(90)=0.014, p(95)=0.020, p(99)=0.097
- vus: min=1.000, max=1.000
