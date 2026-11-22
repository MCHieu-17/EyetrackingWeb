# k6 summary

scenario: outline

- http_req_duration: avg=8.728, min=1.899, med=8.659, max=25.554, p(90)=10.163, p(95)=10.976, p(99)=22.639
- http_req_duration{expected_response:true}: p(90)=10.163, p(95)=10.976, p(99)=22.639, avg=8.728, min=1.899, med=8.659, max=25.554
- http_req_sending: med=0.044, max=0.539, p(90)=0.052, p(95)=0.078, p(99)=0.447, avg=0.066, min=0.012
- http_req_receiving: p(99)=0.199, avg=0.118, min=0.030, med=0.143, max=0.203, p(90)=0.168, p(95)=0.183
- http_req_blocked: min=0.003, med=0.012, max=0.103, p(90)=0.021, p(95)=0.026, p(99)=0.088, avg=0.017
- http_req_waiting: p(95)=10.779, p(99)=22.526, avg=8.545, min=1.855, med=8.430, max=25.463, p(90)=9.998
- http_req_failed: rate=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=1.000, max=1.000
- iterations: rate=4.767, count=20.000
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.072, p(90)=0.000, p(95)=0.004, p(99)=0.058
