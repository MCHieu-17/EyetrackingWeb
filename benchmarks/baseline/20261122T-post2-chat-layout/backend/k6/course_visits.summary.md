# k6 summary

scenario: course_visits

- iterations: count=240.000, rate=23.527
- http_req_duration: avg=9.138, min=2.050, med=8.872, max=23.701, p(90)=13.663, p(95)=14.521, p(99)=17.234
- http_req_blocked: p(95)=0.019, p(99)=0.110, avg=0.013, min=0.001, med=0.011, max=0.146, p(90)=0.013
- http_req_waiting: med=8.529, max=23.602, p(90)=13.439, p(95)=14.151, p(99)=17.132, avg=8.918, min=1.976
- http_req_duration{expected_response:true}: avg=9.138, min=2.050, med=8.872, max=23.701, p(90)=13.663, p(95)=14.521, p(99)=17.234
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- vus: min=5.000, max=5.000
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.102, p(90)=0.000, p(95)=0.000, p(99)=0.089
- http_req_failed: rate=0.000
- http_req_receiving: med=0.144, max=0.637, p(90)=0.349, p(95)=0.414, p(99)=0.461, avg=0.174, min=0.018
- http_req_sending: min=0.005, med=0.041, max=0.792, p(90)=0.055, p(95)=0.066, p(99)=0.299, avg=0.047
